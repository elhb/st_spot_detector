/**
 * logic-handler.js
 * ----------------
 */

import Codes from './viewer/keycodes';
import Vec2 from './viewer/vec2';

/**
 * Abstract class that defines a unified interface for the event handler across
 * different logic handlers.
 */
class LogicHandler {
    constructor() {
        /**
         * FIXME: Have to disable the below for the time being, since new.target
         *        is not supported in uglify-js yet, see
         *        https://github.com/mishoo/UglifyJS2/issues/938 for the bug
         *        tracker issue.
         */

        // if (new.target === LogicHandler)
        //     throw new TypeError(
        //         "Call of new on abstract class LogicHandler not allowed."
        //     );
    }

    /**
     * Abstract method for handling key down events.
     *
     * @param {Object} e - The event object
     */
    processKeydownEvent(e) {
        throw "Abstract method not implemented.";
    }

    /**
     * Abstract method for handling key up events.
     *
     * @param {Object} e - The event object
     */
    processKeyupEvent(e) {
        throw "Abstract method not implemented.";
    }

    /**
     * Abstract method for handling mouse events.
     *
     * @param {Object} e - The event object
     */
    processMouseEvent(e, data) {
        throw "Abstract method not implemented.";
    }

    /**
     * Wraps {@link LogicHandler#processMouseEvent} to record the current mouse
     * position. The mouse position is stored in {@link
     * LogicHandler#_mousePosition}. This may be useful when the logic handler
     * needs to check the mouse position on a key up/down event.
     */
    _recordMousePosition() {
        /**
         * @type {Vec2}
         */
        this._mousePosition = Vec2.Vec2(0, 0);

        var oldM = this.processMouseEvent;
        this.processMouseEvent = (function() {
            return function(e, data) {
                this._mousePosition = data.position;
                return oldM.apply(this, [
                    e,
                    data
                ]);
            };
        })();
    }

    /**
     * Wraps {@link LogicHandler#processKeydownEvent}, {@link
     * LogicHandler#processKeyupEvent}, and {@link
     * LogicHandler#processMouseEvent} to record the current key states. The key
     * states are stored in {@link LogicHandler#_keystates}.
     */
    _recordKeyStates() {
        var keys = {};
        var codeToKey = {};
        for (let key in Codes.keys) {
            keys[key] = false;
            codeToKey[Codes.keyEvent[key]] = key;
        }
        keys.mouseLeft = false;
        keys.mouseRight = false;

        /**
         * @type {Object}
         */
        this._keystates = Object.seal(keys);

        var oldKD = this.processKeydownEvent;
        this.processKeydownEvent = function(e) {
            if (codeToKey[e] in keys)
                keys[codeToKey[e]] = true;
            return oldKD.apply(this, [e]);
        };

        var oldKU = this.processKeyupEvent;
        this.processKeyupEvent = function(e) {
            if (codeToKey[e] in keys)
                keys[codeToKey[e]] = false;
            return oldKU.apply(this, [e]);
        };

        var oldM = this.processMouseEvent;
        this.processMouseEvent = function(e, data) {
            if (e == Codes.mouseEvent.down) {
                switch (data.button) {
                    case Codes.mouseButton.left:
                        keys.mouseLeft = true;
                        break;
                    case Codes.mouseButton.right:
                        keys.mouseRight = true;
                        break;
                }
            } else if (e == Codes.mouseEvent.up) {
                switch (data.button) {
                    case Codes.mouseButton.left:
                        keys.mouseLeft = false;
                        break;
                    case Codes.mouseButton.right:
                        keys.mouseRight = false;
                        break;
                }
            }
            return oldM.apply(this, [e, data]);
        };
    }
}

export default LogicHandler;