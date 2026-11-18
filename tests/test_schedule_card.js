/**
 * Regression tests for TaDiyScheduleCard validation logic.
 * Tests edge cases identified in testing:
 * - "off" acceptance
 * - Rejection of [20], "0x14", booleans, null, "", <5°C, >30°C
 * - Rejection of invalid times (12:99, 24:00 as start)
 * - Safe handling of null blocks
 */

const fs = require('fs');
const assert = require('assert');
const vm = require('vm');

// Minimal mock environment for custom element
global.customElements = { get: () => null, define: () => { } };
global.HTMLElement = class {
  attachShadow() {
    return {
      innerHTML: '',
      getElementById: () => null,
      querySelectorAll: () => [],
      querySelector: () => null,
    };
  }
};

const code = fs.readFileSync('custom_components/tadiy/www/tadiy-schedule-card.js', 'utf8');

vm.runInThisContext(code);

const card = new TaDiyScheduleCard();

console.log("Running TaDiyScheduleCard regression tests...");

// Test _isValidTemp
assert.strictEqual(card._isValidTemp("off"), true, "'off' should be valid");
assert.strictEqual(card._isValidTemp(5), true, "5 should be valid");
assert.strictEqual(card._isValidTemp(30), true, "30 should be valid");
assert.strictEqual(card._isValidTemp(21.5), true, "21.5 should be valid");
assert.strictEqual(card._isValidTemp("21.5"), true, "'21.5' should be valid");

assert.strictEqual(card._isValidTemp([20]), false, "[20] should be rejected");
assert.strictEqual(card._isValidTemp("0x14"), false, "'0x14' hex should be rejected");
assert.strictEqual(card._isValidTemp(null), false, "null should be rejected");
assert.strictEqual(card._isValidTemp(true), false, "true should be rejected");
assert.strictEqual(card._isValidTemp(""), false, "empty string should be rejected");
assert.strictEqual(card._isValidTemp(4), false, "4°C should be rejected (<5)");
assert.strictEqual(card._isValidTemp(31), false, "31°C should be rejected (>30)");
console.log("✓ _isValidTemp checks passed");

// Test _parseMinutes
assert.strictEqual(card._parseMinutes("00:00"), 0, "00:00 should be 0");
assert.strictEqual(card._parseMinutes("12:30"), 750, "12:30 should be 750");
assert.strictEqual(card._parseMinutes("24:00", true), 1440, "24:00 should be 1440 for end time");
assert.strictEqual(card._parseMinutes("24:00", false), null, "24:00 should be rejected as start time");
assert.strictEqual(card._parseMinutes("12:99"), null, "12:99 should be null");
assert.strictEqual(card._parseMinutes("25:00"), null, "25:00 should be null");
console.log("✓ _parseMinutes checks passed");

// Test validateScheduleBlocks with null block protection
const validBlocks = [
  { start_time: "00:00", end_time: "08:00", temperature: 18.0 },
  { start_time: "08:00", end_time: "22:00", temperature: 21.0 },
  { start_time: "22:00", end_time: "24:00", temperature: 18.0 }
];
assert.strictEqual(card.validateScheduleBlocks(validBlocks), null, "valid blocks should pass");

const nullBlockList = [null, { start_time: "08:00", end_time: "24:00", temperature: 21.0 }];
assert.notStrictEqual(card.validateScheduleBlocks(nullBlockList), null, "null block should produce error, not crash");

const startAt24Blocks = [
  { start_time: "24:00", end_time: "24:00", temperature: 18.0 }
];
assert.notStrictEqual(card.validateScheduleBlocks(startAt24Blocks), null, "start at 24:00 should fail");

console.log("✓ validateScheduleBlocks checks passed");
console.log("All schedule card tests passed successfully!");
