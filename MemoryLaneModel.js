.pragma library

var prompts = [
  {id: "where", text: "Where was this?"},
  {id: "who", text: "Who was with you?"},
  {id: "before-after", text: "What happened immediately before or afterward?"},
  {id: "outside-frame", text: "What can the photograph not show?"},
  {id: "kept", text: "Why did you keep this picture?"},
  {id: "past-self", text: "What would you tell your past self?"},
  {id: "detail", text: "What detail do you remember most clearly?"},
  {id: "changed", text: "What has changed since this was taken?"}
]

var KEY_ESCAPE = 0x01000000
var KEY_ENTER = 0x01000004
var KEY_LEFT = 0x01000012
var KEY_RIGHT = 0x01000014
var CONTROL = 0x04000000
var MAX_NOTE_BYTES = 8 * 1024

function utf8ByteLength(value) {
  var text = String(value || "")
  var bytes = 0
  for (var index = 0; index < text.length; index++) {
    var code = text.charCodeAt(index)
    if (code <= 0x7f) {
      bytes += 1
    } else if (code <= 0x7ff) {
      bytes += 2
    } else if (code >= 0xd800 && code <= 0xdbff
               && index + 1 < text.length
               && text.charCodeAt(index + 1) >= 0xdc00
               && text.charCodeAt(index + 1) <= 0xdfff) {
      bytes += 4
      index += 1
    } else {
      bytes += 3
    }
  }
  return bytes
}

function truncateUtf8(value, maxBytes) {
  var text = String(value || "")
  if (utf8ByteLength(text) <= maxBytes) return text
  var end = 0
  var bytes = 0
  while (end < text.length) {
    var code = text.charCodeAt(end)
    var width = code <= 0x7f ? 1 : (code <= 0x7ff ? 2 : 3)
    var characters = 1
    if (code >= 0xd800 && code <= 0xdbff
        && end + 1 < text.length
        && text.charCodeAt(end + 1) >= 0xdc00
        && text.charCodeAt(end + 1) <= 0xdfff) {
      width = 4
      characters = 2
    }
    if (bytes + width > maxBytes) break
    bytes += width
    end += characters
  }
  return text.substring(0, end)
}

function appendBounded(current, chunk, maxBytes) {
  var value = String(current || "") + String(chunk || "")
  return utf8ByteLength(value) > maxBytes
    ? {value: "", overflow: true}
    : {value: value, overflow: false}
}

function fileUrl(path) {
  return "file://" + String(path || "").split("/").map(encodeURIComponent).join("/")
}

function dirty(original, current) {
  return String(original || "") !== String(current || "")
}

function cyclePrompt(index, direction) {
  return (index + direction + prompts.length) % prompts.length
}

function formatReflection(timestamp, note) {
  var date = new Date(timestamp)
  if (isNaN(date.getTime())) return String(note || "")
  var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
  var hour = date.getHours()
  var minute = date.getMinutes()
  var minutes = (minute < 10 ? "0" : "") + minute
  var meridiem = hour >= 12 ? "pm" : "am"
  var displayHour = hour % 12 || 12
  return months[date.getMonth()] + " " + date.getDate() + ", " + date.getFullYear()
    + " - " + displayHour + ":" + minutes + meridiem + ": " + String(note || "")
}

function keyboardAction(key, modifiers, editorFocused) {
  if (key === KEY_ESCAPE) return "close"
  if (editorFocused) return key === KEY_ENTER && (modifiers & CONTROL) ? "save" : ""
  if (key === KEY_LEFT) return "previous"
  if (key === KEY_RIGHT) return "next"
  if (key === 83) return "skip"
  if (key === 80) return "prompt"
  if (key === 79) return "reveal"
  return ""
}

if (typeof module !== "undefined") {
  module.exports = {
    MAX_NOTE_BYTES: MAX_NOTE_BYTES,
    prompts: prompts,
    appendBounded: appendBounded,
    cyclePrompt: cyclePrompt,
    fileUrl: fileUrl,
    dirty: dirty,
    formatReflection: formatReflection,
    keyboardAction: keyboardAction,
    truncateUtf8: truncateUtf8,
    utf8ByteLength: utf8ByteLength
  }
}
