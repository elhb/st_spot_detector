# -*- coding: utf-8 -*-

#### INSECURE; DON'T USE ####
import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
#### INSECURE; DON'T USE ####

import ast
import copy
import time

import numpy as np

import bottle
from bottle import BaseRequest, error, get, post, redirect, response, request, \
    route, run, static_file

from imageprocessor import ImageProcessor
from logger import Logger
from sessioncacher import SessionCacher
from spots import Spots
from tilemap import Tilemap
from PIL import Image

import requests
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import LegacyApplicationClient

import warnings
warnings.simplefilter('ignore', Image.DecompressionBombWarning)
Image.MAX_IMAGE_PIXELS=None

from tissue_recognition import recognize_tissue, get_binary_mask, free

from utils import bits_to_ascii

session_cacher = SessionCacher()
image_processor = ImageProcessor()

app = application = bottle.Bottle()

logger = Logger("st_aligner.log", toFile=False)

## OAuth2 stuff
client_id = "st-viewer-client"
with open("clientsecret.txt", 'r') as f:
    client_secret = f.readline().rstrip()
token_url = "https://admin.spatialtranscriptomicsresearch.org/api/oauth/token"
grant_type = "password"
authorized = False
##

def valid_token(token):
    token_string = "Bearer %s" % token
    request_url = "https://admin.spatialtranscriptomicsresearch.org/api/rest/account"
    r = requests.get(request_url, headers={
        'Authorization': token_string
    })
    valid = r.status_code == 200
    return valid

@app.get('/session_id')
def create_session_cache():
    session_cacher.clear_old_sessions(logger) # can be here for now
    new_session_id = session_cacher.create_session_cache()
    logger.log(new_session_id[:20] + ": New session created.")
    logger.log("Current session caches: ")
    for cache in session_cacher.session_caches:
        logger.log(cache.session_id[:20])
    return new_session_id

@app.get('/detect_spots')
def get_spots():
    session_id = request.query['session_id']
    session_cache = session_cacher.get_session_cache(session_id, logger)
    if(session_cache is not None):
        logger.log(session_id[:20] + ": Detecting spots.")
        # ast converts the query strings into python dictionaries
        TL_coords = ast.literal_eval(request.query['TL'])
        BR_coords = ast.literal_eval(request.query['BR'])
        array_size = ast.literal_eval(request.query['array_size'])
        brightness = float(request.query['brightness'])
        contrast = float(request.query['contrast'])
        threshold = float(request.query['threshold'])

        # converts the image into a BW thresholded image for easier
        # keypoint detection

        BCT_image = image_processor.apply_BCT(
            session_cache.spot_image
        )
        keypoints = image_processor.detect_keypoints(BCT_image)
        spots = Spots(TL_coords, BR_coords, array_size,
            session_cache.spot_scaling_factor)
        spots.create_spots_from_keypoints(keypoints, BCT_image,
            session_cache.spot_scaling_factor)

        logger.log(session_id[:20] + ": Spot detection finished.")

        HE_image = session_cache.tissue_image
        if HE_image is not None:
            logger.log(session_id[:20] + ": Running tissue recognition.")
            mask = get_tissue_mask(HE_image)
        else:
            mask = None

        session_cacher.remove_session_cache(session_id, logger)

        spots.calculate_matrix_from_spots()

        return {'spots': spots.wrap_spots(), 'tissue_mask': mask}
    else:
        response.status = 400
        error_message = 'Session ID expired. Please try again.'
        logger.log(session_id[:20] + ": Error. " + error_message)
        return error_message

def get_tissue_mask(image):
    # Downsample to max 500x500
    max_size = np.array([500] * 2, dtype=float)
    ratio = min(min(max_size / image.size), 1)
    new_size = [ratio * s for s in image.size]

    # hack for now whilst spots are based on 20k x 20k image
    ratio = float(500) / float(20000)

    image = image.copy()
    image.thumbnail(new_size, Image.ANTIALIAS)

    # Convert image to numpy matrix and preallocate the mask matrix
    image = np.array(image, dtype=np.uint8)
    mask = np.zeros(image.shape[0:2], dtype=np.uint8)

    # Run tissue recognition
    recognize_tissue(image, mask)
    mask = get_binary_mask(mask)

    # Encode mask to bit string
    bit_string = bits_to_ascii((mask == 255).flatten())

    free(mask)

    return {'data': bit_string, 'shape': new_size, 'scale': ratio}

@app.post('/tiles')
def get_tiles():
    """Here we receive the Cy3 image (and optionally HE image) from the client,
    then firstly scale it to approximately 20k x 20k then rotate it 180°.
    The scaling factor for this is saved and sent to the client.
    The images are tiled and the tilemaps are saved and sent to the client.
    A Cy3 image of approximately 3k x 3k is saved on the server for further
    spot detection later on.
    """
    data = ast.literal_eval(request.body.read())
    image_string = {'cy3': data['cy3_image'], 'he': data['he_image']}
    rotate = True if data['rotate'] == 'true' else False
    session_id = data['session_id']
    session_cache = session_cacher.get_session_cache(session_id, logger)
    if(session_cache is not None):
        valid = {}
        for key, image in image_string.items():
            valid.update({
                key: image_processor.validate_jpeg_URI(image)
            })
        # also do proper type validation here; see
        # https://zubu.re/bottle-security-checklist.html and
        # https://github.com/ahupp/python-magic
        if(valid['cy3']):
            # dict holding Tilemap(s) of Cy3 and HE tiles
            tiles = {}
            for key, image in image_string.items():
                if not valid[key]:
                    continue

                logger.log(session_id[:20] + ": Transforming " + key + " image.")
                image = image_processor.jpeg_URI_to_Image(image)
                image_size = image.size
                # rotated and scaled down to 20k x 20k
                image, scaling_factor = image_processor.transform_original_image(image, rotate)

                logger.log(session_id[:20] + ": Tiling " + key + " images.")
                tiles_ = Tilemap()
                for x in tiles_.tilemapLevels:
                    tiles_.put_tiles_at(x,
                        image_processor.tile_image(image, x))

                session_cache.tiles[key] = tiles_

                if(key == 'cy3'):
                    # we want to save a scaled down version of the image
                    # for spot detection later :)
                    spot_img, spot_sf = image_processor.resize_image(image,
                        [4000, 4000])
                    session_cache.spot_image = spot_img
                    session_cache.spot_scaling_factor = spot_sf

                if(key == 'he'):
                    # also save a scaled down version of the tissue image
                    tissue_img = image_processor.resize_image(image,
                        [500, 500])[0]
                    session_cache.tissue_image = tissue_img

                tiles.update({
                    key: {
                        'histogram': image.histogram(),
                        # we want to send back the scaling factor of the image to
                        # the client, so it can convert its spot data back to the
                        # original image size.
                        # if the image is scaled down to 4k the scaling factor
                        # will for example be 20k / 4k, i.e. 5
                        'scaling_factor': scaling_factor,
                        'image_size': image_size,
                        'tiles': tiles_.tilemaps,
                    },
                })
                logger.log(session_id[:20] + ": Image tiling complete.")
            #TODO: make sure the large images get cleared out of the memory
        else:
            response.status = 400
            error_message = 'Invalid Cy3 image. Please upload a jpeg image.'
            logger.log(session_id[:20] + ": Error. " + error_message + "")
            return error_message
    else:
        response.status = 400
        error_message = 'Session ID expired. Please try again.'
        logger.log(session_id[:20] + ": Error. " + error_message)
        return error_message

    ret = {
        'tiles': tiles,
        'levels': Tilemap.tilemapLevels,
        'dim': [Tilemap.tileWidth, Tilemap.tileHeight],
    }
    return ret

@app.route('/loginerr')
@app.route('/loginerr/<filepath:path>')
def loginerr(filepath='index.html'):
    access_token = request.get_cookie("access_token")

    if valid_token(access_token):
        redirect('/')
    else:
        return static_file(filepath, root='../client/devel/login')

@app.route('/login')
@app.route('/login/<filepath:path>')
def login(filepath='index.html'):
    access_token = request.get_cookie("access_token")

    if valid_token(access_token):
        redirect('/')
    else:
        return static_file(filepath, root='../client/devel/login')

@app.post('/loginpost')
def loginpost():
    user = request.forms.get("j_username")
    pw = request.forms.get("j_password")

    r = requests.post(token_url, data={
        'grant_type': 'password',
        'username': user,
        'password': pw,
        'client_id': client_id,
        'client_secret': client_secret
    })

    json_payload = r.json()

    if r.status_code == 200:
        access_token = json_payload['access_token']
        refresh_token = json_payload['refresh_token']
        expiry_time = json_payload['expires_in']

        print("Successful login by %s with token %s" % (user, access_token))

        # must set cookies after creating static file since creating this
        # object resets the headers
        filepath='index.html'
        response.set_cookie("access_token", access_token, path='/')
        redirect('/')
    else:
        print("Failed to authenticate because of %s: %s" % (r.reason, json_payload['error_description']))
        redirect('loginerr/')

@app.route('/')
@app.route('/<filepath:path>')
def serve_site(filepath='index.html'):
    access_token = request.get_cookie("access_token")
    if valid_token(access_token):
        return static_file(filepath, root='../client/devel')
    else:
        redirect('/login')

@app.error(404)
def error404(error):
    return "404 Not Found"

if __name__ == "__main__": # if this file is run from the terminal
    app.run(host='0.0.0.0', port=8080, debug=True, reloader=True)
