import QtQuick
import Quickshell
import Quickshell.Io
import "MemoryLaneModel.js" as Model

Item {
  id: root

  property var shell: null
  property var manifest: null
  property bool ready: false
  property bool failed: false
  property bool scanRunning: false
  property string scanMessage: ""
  property var scanProgress: ({seen: 0, eligible: 0, errors: 0})
  property var status: ({onboarded: false, eligibleCount: 0})
  property string lastError: ""

  property int nextId: 1
  property var callbacks: ({})
  property var queued: []
  property string chooserOutput: ""
  property bool chooserOverflow: false
  property var chooserCallback: null
  property bool choosingPhoto: false
  property string responseBuffer: ""
  property string errorBuffer: ""

  readonly property int maxFrameBytes: 16 * 1024

  readonly property string backendPath: decodeURIComponent(
    Qt.resolvedUrl("backend/memory_lane_backend.py").toString().replace(/^file:\/\//, ""))

  function call(method, params, callback) {
    if (failed) {
      if (callback)
        callback(null, {message: lastError})
      return -1
    }
    var request = {
      id: nextId++,
      method: method,
      params: params || {}
    }
    if (Model.utf8ByteLength(JSON.stringify(request) + "\n") > maxFrameBytes) {
      lastError = "The request is too large."
      if (callback)
        callback(null, {message: lastError})
      return -1
    }
    callbacks[request.id] = callback || function() {}
    if (!ready)
      queued.push(request)
    else
      backend.write(JSON.stringify(request) + "\n")
    return request.id
  }

  function flush() {
    var pending = queued
    queued = []
    for (var index = 0; index < pending.length; index++)
      backend.write(JSON.stringify(pending[index]) + "\n")
  }

  function failPending(message) {
    lastError = message
    var pending = callbacks
    callbacks = ({})
    queued = []
    for (var requestId in pending)
      pending[requestId](null, {message: message})
  }

  function failService(message) {
    startupTimeout.stop()
    failed = true
    ready = false
    scanRunning = false
    responseBuffer = ""
    errorBuffer = ""
    failPending(message)
  }

  function collectBackendOutput(chunk, isError) {
    if (failed)
      return
    var parsed = Model.consumeLines(isError ? errorBuffer : responseBuffer,
      chunk, maxFrameBytes, function(line) {
        if (root.failed)
          return
        if (isError)
          root.lastError = String(line).replace(/\/[^ ]+/g, "[path]").substring(0, 240)
        else
          root.handle(line)
      })
    if (parsed.overflow) {
      failService("The local photo service exceeded its output limit.")
      backend.running = false
    } else if (!failed) {
      if (isError)
        errorBuffer = parsed.value
      else
        responseBuffer = parsed.value
    }
  }

  function handle(line) {
    var message
    try {
      message = JSON.parse(String(line))
    } catch (error) {
      failService("The local photo service returned invalid data.")
      backend.running = false
      return
    }
    if (!message || typeof message !== "object" || Array.isArray(message)) {
      failService("The local photo service returned invalid data.")
      backend.running = false
      return
    }

    if (message.event === "ready") {
      if (failed)
        return
      startupTimeout.stop()
      ready = true
      flush()
      initialize()
      return
    }
    if (message.event === "scan.progress") {
      scanRunning = true
      scanProgress = message.data
      return
    }
    if (message.event === "scan.complete") {
      scanRunning = false
      scanProgress = message.data
      scanMessage = "Scan complete · " + (message.data.added || 0) + " new photos"
        + (message.data.errors ? " · " + message.data.errors + " unreadable items" : "")
      refreshStatus()
      return
    }
    if (message.event === "scan.error") {
      scanRunning = false
      lastError = message.data.message || "Scan failed."
      scanMessage = "Scan failed. " + lastError
      return
    }

    var callback = callbacks[message.id]
    delete callbacks[message.id]
    if (!message.ok)
      lastError = message.error && message.error.message
        ? message.error.message
        : "The action failed."
    if (callback)
      callback(message.ok ? message.result : null, message.error || null)
  }

  function initialize() {
    call("app.initialize", {}, function(result) {
      if (result)
        status = result
    })
  }

  function refreshStatus() {
    call("app.status", {}, function(result) {
      if (result)
        status = result
    })
  }

  function suggestedRoot(callback) {
    call("library.suggestedRoot", {}, callback)
  }

  function addRoot(path, callback) {
    call("library.rootAdd", {path: path}, function(result, error) {
      if (result)
        status = result
      if (callback)
        callback(result, error)
    })
  }

  function chooseRoot(callback) {
    if (chooser.running)
      return
    chooserOutput = ""
    chooserOverflow = false
    chooserCallback = callback || null
    choosingPhoto = false
    chooser.running = true
  }

  function choosePhoto(callback) {
    if (chooser.running) {
      callback(null, {message: "A file chooser is already open."})
      return
    }
    chooserOutput = ""
    chooserOverflow = false
    chooserCallback = callback
    choosingPhoto = true
    chooser.running = true
  }

  function collectChooserOutput(chunk) {
    var collected = Model.appendBounded(chooserOutput, chunk, maxFrameBytes)
    if (!collected.overflow) {
      chooserOutput = collected.value
      return
    }
    chooserOverflow = true
    chooserOutput = ""
    lastError = "The folder chooser returned too much data."
    chooser.running = false
  }

  function scan() {
    if (scanRunning)
      return
    scanRunning = true
    scanMessage = "Scanning folders…"
    call("library.scanStart", {}, function(result, error) {
      if (!result) {
        scanRunning = false
        scanMessage = error ? error.message : "Could not start scanning."
      }
    })
  }

  function nextMemory(callback) {
    call("memory.next", {}, callback)
  }

  function ensurePreview(photoId, callback) {
    call("preview.ensure", {photoId: photoId}, callback)
  }

  function shown(photoId) {
    call("memory.shown", {photoId: photoId})
  }

  function skip(photoId, callback) {
    call("memory.skip", {photoId: photoId}, callback)
  }

  function saveDraft(photoId, promptId, note) {
    call("draft.save", {photoId: photoId, promptId: promptId, note: note})
  }

  function saveReflection(photoId, promptId, promptText, note, callback) {
    call("reflection.save", {
      photoId: photoId,
      promptId: promptId,
      promptText: promptText,
      note: note
    }, callback)
  }

  function revealOriginal(photoId) {
    call("original.reveal", {photoId: photoId})
  }

  function photoLocation(photoId, callback) {
    call("photo.location", {photoId: photoId}, callback)
  }

  Process {
    id: chooser
    command: root.choosingPhoto
      ? ["omarchy-file-select", "--title", "Open a photo from an approved folder", "--extensions", "jpg jpeg png webp"]
      : ["omarchy-file-select", "--directory"]
    stdout: SplitParser {
      // An empty marker forwards chunks immediately instead of buffering until exit.
      splitMarker: ""
      onRead: function(chunk) {
        root.collectChooserOutput(chunk)
      }
    }
    onExited: function(exitCode) {
      var callback = root.chooserCallback
      var selectedPath = root.chooserOutput.trim()
      var overflow = root.chooserOverflow
      root.chooserCallback = null
      root.chooserOutput = ""
      root.chooserOverflow = false
      if (overflow || exitCode !== 0 || !selectedPath) {
        if (callback)
          callback(null, overflow || exitCode > 1 ? {message: "Could not select the photo or folder."} : null)
        return
      }
      if (root.choosingPhoto) {
        root.call("memory.open", {path: selectedPath}, callback)
        return
      }
      root.addRoot(selectedPath, function(result, error) {
        if (result)
          root.scan()
        if (callback)
          callback(result, error)
      })
    }
  }

  Process {
    id: backend
    stdinEnabled: true
    command: ["/usr/bin/python3", root.backendPath]
    running: root.backendPath !== ""
    stdout: SplitParser {
      splitMarker: ""
      onRead: function(chunk) {
        root.collectBackendOutput(chunk, false)
      }
    }
    stderr: SplitParser {
      splitMarker: ""
      onRead: function(chunk) {
        root.collectBackendOutput(chunk, true)
      }
    }
    onExited: function(exitCode) {
      if (!root.failed)
        root.failService("Memory Lane's local service stopped. Reload the shell to restart it.")
    }
  }

  Timer {
    id: startupTimeout
    interval: 10000
    running: true
    repeat: false
    onTriggered: {
      root.failService("Memory Lane's local service did not start within 10 seconds. Reload the shell to retry.")
      backend.running = false
    }
  }
}
