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
    prompts: prompts,
    cyclePrompt: cyclePrompt,
    fileUrl: fileUrl,
    dirty: dirty,
    formatReflection: formatReflection,
    keyboardAction: keyboardAction
  }
}
