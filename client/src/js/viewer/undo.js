/**
 * undo.js
 * ----------------
 */

import math from 'mathjs';
import $ from 'jquery';

/**
 * Data structure for actions which can be undone
 */
class UndoAction {
    /**
     * Constructs a new Undo action
     *
     * @param {string} tab - In which tab it occured
     * @param {string} action - The type of action
     * @param {object} state - The previous state associated with the action
     */
    constructor(tab, action, state) {
        this.tab = tab;
        this.action = action;
        this.state = state;
    }
}

/**
 * Data structure for an undo stack and various utility functions associated with it
 */
class UndoStack {
    /**
     * Constructs a new Undo stack
     *
     * @param {HTMLElement} canvas - The canvas element
     * @param {object} defaultModifiers - Default modifiers
     */
    constructor() {
        /**
         * The stack.
         * @type {Array}
         */
        this.stack = [];
        this.redoStack = [];
    }

    /**
     * Push to the stack.
     *
     * @param {Action} action - The action last performed.
     */
    push(action) {
        // clear the redo stack if actions are being performed
        this.redoStack = []
        this.stack.push(action);
        console.log("puuuuuuuuuush!!")
    }

    /**
     * Pop from the stack.
     *
     * @returns {Action} action - The action last performed.
     */
    pop() {
        console.log("popping pop pop pop!")
        this.redoStack.push(this.stack.slice(-1)[0])
        return this.stack.pop()
    }

    /**
     * Get the tab value of the last item in the stack.
     *
     * @returns {String} tab - The tab of the last action performed. If the stack is empty, then undefined is returned.
     */
    lastTab() {
        if(this.stack.length == 0)
            return undefined;
        else
            return this.stack.slice(-1)[0].tab;
    }

    /**
     * Get the action value of the last item in the stack.
     *
     * @returns {String} action - The action of the last action performed. If the stack is empty, then undefined is returned.
     */
    lastAction() {
        if(this.stack.length == 0)
            return undefined;
        else
            return this.stack.slice(-1)[0].action;
    }
}

export { UndoAction };
export default UndoStack;