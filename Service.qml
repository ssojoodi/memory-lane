import QtQuick
import Quickshell
import Quickshell.Io

Item {
  id: root

  property var shell: null
  property var manifest: null
  property bool ready: false
  property bool scanRunning: false
  property var scanProgress: ({seen: 0, eligible: 0, errors: 0})
  property var status: ({onboarded: false, roots: [], eligibleCount: 0})
  property string lastError: ""

  property int nextId: 1
  property var callbacks: ({})
  property var queued: []
  property string chooserOutput: ""
  property var chooserCallback: null

  readonly property string backendPath: manifest && manifest.__sourceDir
    ? manifest.__sourceDir + "/backend/memory_lane_backend.py"
    : ""

  function call(method, params, callback) {
    var request = {
      id: nextId++,
      method: method,
      params: params || {}
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

  function handle(line) {
    var message
    try {
      message = JSON.parse(String(line))
    } catch (error) {
      lastError = "The local photo service returned invalid data."
      return
    }

    if (message.event === "ready") {
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
      refreshStatus()
      return
    }
    if (message.event === "scan.error") {
      scanRunning = false
      lastError = message.data.message || "Scan failed."
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
    chooserCallback = callback || null
    chooser.running = true
  }

  function scan() {
    call("library.scanStart", {}, function(result) {
      if (result)
        scanRunning = true
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

  function openOriginal(photoId) {
    call("original.open", {photoId: photoId})
  }

  Process {
    id: chooser
    command: ["omarchy-file-select", "--directory"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.chooserOutput = text.trim()
    }
    onExited: function(exitCode) {
      var callback = root.chooserCallback
      root.chooserCallback = null
      if (exitCode !== 0 || !root.chooserOutput) {
        if (callback)
          callback(null)
        return
      }
      root.addRoot(root.chooserOutput, function(result, error) {
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
      onRead: function(line) {
        root.handle(line)
      }
    }
    stderr: SplitParser {
      onRead: function(line) {
        var sanitized = String(line).replace(/\/[^ ]+/g, "[path]")
        root.lastError = sanitized.substring(0, 240)
      }
    }
    onExited: function(exitCode) {
      root.ready = false
      if (exitCode !== 0)
        root.failPending("Memory Lane's local service stopped. Reload the shell to restart it.")
    }
  }
}
