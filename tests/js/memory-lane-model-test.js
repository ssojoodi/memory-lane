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
