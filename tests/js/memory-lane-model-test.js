const assert = require("assert")
const fs = require("fs")
const vm = require("vm")
let source = fs.readFileSync("MemoryLaneModel.js", "utf8").replace(/^\.pragma library\s*/m, "")
const sandbox = {module:{exports:{}}}
vm.runInNewContext(source, sandbox)
const model = sandbox.module.exports
assert.equal(model.dirty("a", "b"), true)
assert.equal(model.dirty("a", "a"), false)
assert.equal(model.cyclePrompt(0, -1), model.prompts.length - 1)
assert.equal(model.cyclePrompt(model.prompts.length - 1, 1), 0)
assert.equal(model.formatReflection("2026-08-19T22:56:00", "This is a temple in Japan."), "Aug 19, 2026 - 10:56pm: This is a temple in Japan.")
assert.equal(model.formatReflection("not-a-date", "A memory"), "A memory")
assert.equal(model.keyboardAction(83, 0, false), "skip")
assert.equal(model.keyboardAction(0x01000012, 0, false), "previous")
assert.equal(model.keyboardAction(0x01000014, 0, false), "next")
assert.equal(model.keyboardAction(0x01000012, 0, true), "")
assert.equal(model.keyboardAction(83, 0, true), "")
assert.equal(model.keyboardAction(79, 0, false), "reveal")
assert.equal(model.keyboardAction(82, 0, false), "rotate")
assert.equal(model.keyboardAction(82, 0, true), "")
assert.equal(model.rotateQuarterTurn(0), 90)
assert.equal(model.rotateQuarterTurn(270), 0)
assert.equal(model.fileUrl("/tmp/a b.jpg"), "file:///tmp/a%20b.jpg")
assert.equal(model.utf8ByteLength("memory"), 6)
assert.equal(model.utf8ByteLength("café"), 5)
assert.equal(model.utf8ByteLength("📷"), 4)
assert.equal(model.truncateUtf8("ab📷cd", 6), "ab📷")
assert.deepEqual(
  model.appendBounded("1234", "5678", 8),
  {value: "12345678", overflow: false}
)
assert.deepEqual(
  model.appendBounded("1234", "56789", 8),
  {value: "", overflow: true}
)
console.log("MemoryLaneModel tests passed")

let lines = []
let frame = model.consumeLines("", "ab", 5, line => lines.push(line))
assert.equal(frame.value, "ab")
frame = model.consumeLines(frame.value, "cd\nx\ny", 5, line => lines.push(line))
assert.deepEqual(lines, ["abcd", "x"])
assert.equal(frame.value, "y")
assert.equal(model.consumeLines("abcd", "e", 5, () => assert.fail()).overflow, true)
assert.equal(model.consumeLines("", "éé\n", 5, () => {}).overflow, false)
assert.equal(model.consumeLines("", "ééé", 5, () => assert.fail()).overflow, true)
assert.equal(model.consumeLines("", "x".repeat(100000), 16384, () => assert.fail()).overflow, true)
assert.equal(model.consumeLines("", "x\n".repeat(20000), 5, () => {}).overflow, false)
