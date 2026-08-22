import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.Commons
import qs.Ui
import "MemoryLaneModel.js" as Model

Item {
  id: root

  property var shell: null
  property var manifest: null
  property var service: null

  property bool opened: false
  property bool actionPending: false
  property string view: "loading"
  property string message: ""
  property string suggestedPath: ""
  property int promptIndex: 0
  property int requestToken: 0

  property var sessionEntries: []
  property int sessionIndex: -1
  property var currentEntry: null
  property string initialNote: ""

  readonly property var prompt: Model.prompts[promptIndex]
  readonly property var currentMemory: currentEntry ? currentEntry.memory : null
  readonly property var reflection: currentEntry ? currentEntry.reflection : null
  readonly property string previewPath: currentEntry ? currentEntry.previewPath : ""

  function acquireService() {
    if (!service && shell && manifest)
      service = shell.serviceFor(manifest.id)
    return service
  }

  function makeEntry(memory) {
    var note = memory.reflection
      ? memory.reflection.note
      : (memory.draft ? memory.draft.note : "")
    return {
      memory: memory,
      note: note || "",
      reflection: memory.reflection || null,
      previewPath: ""
    }
  }

  function copyEntry(entry, note, reflection, previewPath) {
    return {
      memory: entry.memory,
      note: note,
      reflection: reflection,
      previewPath: previewPath
    }
  }

  function replaceEntry(index, entry) {
    var updated = sessionEntries.slice()
    updated[index] = entry
    sessionEntries = updated
  }

  function beginRequest() {
    requestToken += 1
    actionPending = true
    return requestToken
  }

  function open(payloadJson) {
    opened = true
    actionPending = false
    message = ""
    sessionEntries = []
    sessionIndex = -1
    currentEntry = null
    requestToken += 1
    if (!acquireService()) {
      view = "loading"
      serviceRetry.restart()
      return
    }
    begin()
  }

  function begin() {
    if (!service.ready) {
      view = "loading"
      readyRetry.restart()
      return
    }
    if (!service.status.onboarded) {
      view = "onboarding"
      service.suggestedRoot(function(result) {
        suggestedPath = result ? result.path : ""
      })
      return
    }
    loadMemory()
  }

  function loadMemory() {
    var token = beginRequest()
    view = "loading"
    message = ""
    service.nextMemory(function(result) {
      if (!opened || token !== requestToken)
        return
      if (!result || !result.memory) {
        actionPending = false
        view = "empty"
        message = result ? result.reason : service.lastError
        return
      }
      var entries = sessionEntries.slice(0, sessionIndex + 1)
      var entry = makeEntry(result.memory)
      entries.push(entry)
      sessionEntries = entries
      showEntry(entry, entries.length - 1, true, token)
    })
  }

  function showEntry(entry, index, markShown, existingToken) {
    var token = existingToken || beginRequest()
    view = "loading"
    sessionIndex = index
    currentEntry = entry
    noteEditor.text = entry.note
    initialNote = entry.note

    function reveal(path) {
      if (!opened || token !== requestToken)
        return
      var updated = copyEntry(entry, entry.note, entry.reflection, path)
      replaceEntry(index, updated)
      currentEntry = updated
      actionPending = false
      view = "memory"
      if (markShown)
        service.shown(updated.memory.id)
      Qt.callLater(function() {
        if (root.opened && root.view === "memory")
          keyboardScope.forceActiveFocus()
      })
    }

    if (entry.previewPath) {
      reveal(entry.previewPath)
      return
    }
    service.ensurePreview(entry.memory.id, function(preview) {
      if (!opened || token !== requestToken)
        return
      if (!preview) {
        actionPending = false
        view = "error"
        message = service.lastError
        return
      }
      reveal(preview.path)
    })
  }

  function captureCurrentNote() {
    if (!currentEntry)
      return
    var note = noteEditor.text
    var updated = copyEntry(
      currentEntry,
      note,
      currentEntry.reflection,
      currentEntry.previewPath
    )
    replaceEntry(sessionIndex, updated)
    currentEntry = updated
    if (Model.dirty(initialNote, note))
      service.saveDraft(currentMemory.id, prompt.id, note)
    initialNote = note
  }

  function advance() {
    if (sessionIndex < sessionEntries.length - 1)
      showEntry(sessionEntries[sessionIndex + 1], sessionIndex + 1, false)
    else
      loadMemory()
  }

  function previousMemory() {
    if (view !== "memory" || actionPending || sessionIndex <= 0)
      return
    captureCurrentNote()
    showEntry(sessionEntries[sessionIndex - 1], sessionIndex - 1, false)
  }

  function nextMemory() {
    if (view !== "memory" || actionPending || !currentEntry)
      return
    captureCurrentNote()
    advance()
  }

  function save() {
    if (view !== "memory" || actionPending || !currentEntry)
      return
    var entry = currentEntry
    var index = sessionIndex
    var note = noteEditor.text
    var selectedPrompt = prompt
    var token = beginRequest()
    view = "loading"
    service.saveReflection(
      entry.memory.id,
      selectedPrompt.id,
      selectedPrompt.text,
      note,
      function(result) {
        if (!opened || token !== requestToken)
          return
        if (!result) {
          actionPending = false
          view = "error"
          message = service.lastError
          return
        }
        var savedReflection = {
          note: note,
          prompt_id: selectedPrompt.id,
          prompt_text: selectedPrompt.text,
          updated_at: result.savedAt
        }
        var updated = copyEntry(entry, note, savedReflection, entry.previewPath)
        replaceEntry(index, updated)
        currentEntry = updated
        initialNote = note
        actionPending = false
        advance()
      }
    )
  }

  function skip() {
    if (view !== "memory" || actionPending || !currentEntry)
      return
    captureCurrentNote()
    var photoId = currentMemory.id
    var token = beginRequest()
    view = "loading"
    service.skip(photoId, function(result) {
      if (!opened || token !== requestToken)
        return
      if (!result) {
        actionPending = false
        view = "error"
        message = service.lastError
        return
      }
      actionPending = false
      advance()
    })
  }

  function revealOriginal() {
    if (view !== "memory" || actionPending || !currentMemory)
      return
    var photoId = currentMemory.id
    dismiss()
    service.revealOriginal(photoId)
  }

  function close() {
    requestToken += 1
    actionPending = false
    if (currentEntry && view === "memory")
      captureCurrentNote()
    opened = false
  }

  function dismiss() {
    close()
    if (shell && typeof shell.hide === "function")
      shell.hide((manifest && manifest.id) || "sojoodi.memory-lane")
  }

  function toggle() {
    if (opened)
      dismiss()
    else
      open("{}")
  }

  Timer {
    id: serviceRetry
    interval: 80
    repeat: false
    onTriggered: {
      if (root.acquireService())
        root.begin()
      else {
        root.view = "error"
        root.message = "Memory Lane could not reach its local service."
      }
    }
  }

  Timer {
    id: readyRetry
    interval: 120
    repeat: false
    onTriggered: root.begin()
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors {
      top: true
      bottom: true
      left: true
      right: true
    }
    color: "transparent"
    WlrLayershell.namespace: "memory-lane"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    exclusionMode: ExclusionMode.Ignore

    Rectangle {
      anchors.fill: parent
      color: Color.menu.scrim
    }

    MouseArea {
      anchors.fill: parent
      onClicked: root.dismiss()
    }

    BorderSurface {
      id: card
      anchors.centerIn: parent
      width: Math.min(panel.width - Style.gapsOut * 2, Style.space(980))
      height: Math.min(panel.height - Style.gapsOut * 2, Style.space(650))
      color: Color.menu.background
      radius: Style.cornerRadius
      borderSpec: Border.surfaceSpec(
        "menu",
        "border",
        Color.menu.border,
        Math.max(1, Style.space(2))
      )
      padding: Style.spacing.panelPadding

      MouseArea {
        anchors.fill: parent
        onClicked: {}
      }

      Item {
        id: keyboardScope
        anchors.fill: parent
        anchors.margins: Style.spacing.panelPadding
        focus: true
        Keys.priority: Keys.BeforeItem
        Keys.onPressed: function(event) {
          var action = Model.keyboardAction(
            event.key,
            event.modifiers,
            noteEditor.activeFocus
          )
          if (action === "close")
            root.dismiss()
          else if (action === "save")
            root.save()
          else if (action === "skip")
            root.skip()
          else if (action === "previous")
            root.previousMemory()
          else if (action === "next")
            root.nextMemory()
          else if (action === "prompt")
            root.promptIndex = (root.promptIndex + 1) % Model.prompts.length
          else if (action === "reveal")
            root.revealOriginal()
          else
            return
          event.accepted = true
        }

        Column {
          anchors.fill: parent
          spacing: 0

          Item {
            width: parent.width
            height: parent.height

            Column {
              visible: root.view === "loading"
              anchors.centerIn: parent
              spacing: Style.space(12)

              Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Finding a memory…"
                color: Color.menu.text
                font.pixelSize: Style.font.heading
              }
            }

            Column {
              visible: root.view === "onboarding"
              anchors.centerIn: parent
              width: Math.min(parent.width, Style.space(560))
              spacing: Style.space(16)

              Text {
                width: parent.width
                text: "Your photos stay here"
                color: Color.menu.text
                font.pixelSize: Style.font.title
                horizontalAlignment: Text.AlignHCenter
              }

              Text {
                width: parent.width
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                color: Color.menu.text
                opacity: .72
                text: "Memory Lane reads only folders you approve. Notes and previews stay on this computer, and original photographs are never changed or uploaded."
              }

              Text {
                width: parent.width
                elide: Text.ElideMiddle
                horizontalAlignment: Text.AlignHCenter
                color: Color.menu.text
                text: root.suggestedPath
              }

              Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: Style.space(10)

                Button {
                  text: "Use Pictures"
                  enabled: root.suggestedPath !== ""
                  onClicked: service.addRoot(root.suggestedPath, function(result) {
                    if (result) {
                      service.scan()
                      root.view = "scanning"
                    }
                  })
                }

                Button {
                  text: "Choose folder…"
                  onClicked: {
                    root.view = "scanning"
                    service.chooseRoot(function(result) {
                      if (!result)
                        root.view = "onboarding"
                    })
                  }
                }
              }
            }

            Column {
              visible: root.view === "scanning"
              anchors.centerIn: parent
              spacing: Style.space(10)

              Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Looking through your approved folder…"
                color: Color.menu.text
                font.pixelSize: Style.font.heading
              }

              Text {
                anchors.horizontalCenter: parent.horizontalCenter
                color: Color.menu.text
                opacity: .7
                text: service ? service.scanProgress.eligible + " photographs found" : ""
              }

              Button {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Show a photo"
                enabled: service && !service.scanRunning
                onClicked: root.loadMemory()
              }
            }

            Column {
              visible: root.view === "memory"
              anchors.fill: parent
              spacing: Style.space(10)

              Rectangle {
                width: parent.width
                height: Math.max(
                  Style.space(320),
                  parent.height - annotationArea.height - parent.spacing
                )
                color: Qt.rgba(0, 0, 0, .22)
                radius: Style.cornerRadius

                Image {
                  anchors.fill: parent
                  anchors.margins: Style.space(8)
                  source: root.previewPath ? Model.fileUrl(root.previewPath) : ""
                  fillMode: Image.PreserveAspectFit
                  asynchronous: true
                  cache: false
                }
              }

              Column {
                id: annotationArea
                width: parent.width
                spacing: Style.space(8)

                Rectangle {
                  visible: root.reflection !== null
                  width: parent.width
                  height: visible ? memoryText.implicitHeight + Style.space(16) : 0
                  color: Qt.rgba(1, 1, 1, .07)
                  radius: Style.cornerRadius
                  border.color: Qt.rgba(
                    Color.menu.text.r,
                    Color.menu.text.g,
                    Color.menu.text.b,
                    .16
                  )

                  Text {
                    id: memoryText
                    anchors.fill: parent
                    anchors.margins: Style.space(8)
                    wrapMode: Text.WordWrap
                    color: Color.menu.text
                    opacity: .82
                    font.pixelSize: Style.font.body
                    text: root.reflection
                      ? Model.formatReflection(
                          root.reflection.updated_at,
                          root.reflection.note
                        )
                      : ""
                  }
                }

                Row {
                  width: parent.width
                  height: Style.space(58)
                  spacing: Style.space(8)

                  Rectangle {
                    id: promptControl
                    width: parent.width * .36
                    height: parent.height
                    color: Qt.rgba(1, 1, 1, .05)
                    radius: Style.cornerRadius
                    border.color: Color.menu.border

                    Row {
                      anchors.fill: parent
                      anchors.margins: Style.space(5)
                      spacing: Style.space(5)

                      Button {
                        id: previousPrompt
                        text: "<"
                        tooltipText: "Previous prompt"
                        horizontalPadding: Style.space(8)
                        verticalPadding: Style.space(4)
                        onClicked: root.promptIndex = Model.cyclePrompt(root.promptIndex, -1)
                      }

                      Text {
                        width: parent.width - previousPrompt.width - nextPrompt.width - parent.spacing * 2
                        anchors.verticalCenter: parent.verticalCenter
                        elide: Text.ElideRight
                        horizontalAlignment: Text.AlignHCenter
                        text: root.prompt.text
                        color: Color.menu.text
                        font.pixelSize: Style.font.body
                      }

                      Button {
                        id: nextPrompt
                        text: ">"
                        tooltipText: "Next prompt"
                        horizontalPadding: Style.space(8)
                        verticalPadding: Style.space(4)
                        onClicked: root.promptIndex = Model.cyclePrompt(root.promptIndex, 1)
                      }
                    }
                  }

                  Rectangle {
                    width: parent.width - promptControl.width - actions.width - parent.spacing * 2
                    height: parent.height
                    color: Qt.rgba(1, 1, 1, .05)
                    radius: Style.cornerRadius
                    border.color: Color.menu.border

                    TextEdit {
                      id: noteEditor
                      anchors.fill: parent
                      anchors.margins: Style.space(8)
                      clip: true
                      color: Color.menu.text
                      font.pixelSize: Style.font.body
                      wrapMode: TextEdit.Wrap
                      selectByMouse: true
                      textFormat: TextEdit.PlainText
                      onTextChanged: {
                        var limited = Model.truncateUtf8(text, Model.MAX_NOTE_BYTES)
                        if (limited !== text) {
                          var position = Math.min(cursorPosition, limited.length)
                          text = limited
                          cursorPosition = position
                        }
                      }
                    }

                    Text {
                      visible: noteEditor.text.length === 0
                      anchors.left: parent.left
                      anchors.top: parent.top
                      anchors.margins: Style.space(8)
                      text: "What do you remember?"
                      color: Color.menu.text
                      opacity: .45
                    }
                  }

                  Row {
                    id: actions
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: Style.space(6)

                    Button {
                      iconText: "󰆓"
                      tooltipText: "Save memory"
                      fontFamily: "Symbols Nerd Font Mono"
                      onClicked: root.save()
                    }

                    Button {
                      iconText: "󰁔"
                      tooltipText: "Skip photo"
                      fontFamily: "Symbols Nerd Font Mono"
                      onClicked: root.skip()
                    }

                    Button {
                      iconText: "󰍉"
                      tooltipText: "Show in Files"
                      fontFamily: "Symbols Nerd Font Mono"
                      onClicked: root.revealOriginal()
                    }
                  }
                }
              }
            }

            Column {
              visible: ["empty", "error"].indexOf(root.view) !== -1
              anchors.centerIn: parent
              width: Math.min(parent.width, Style.space(540))
              spacing: Style.space(16)

              Text {
                width: parent.width
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                text: root.message || (service ? service.lastError : "")
                color: Color.menu.text
                font.pixelSize: Style.font.heading
              }

              Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: Style.space(10)

                Button {
                  text: "Rescan"
                  onClicked: {
                    service.scan()
                    root.view = "scanning"
                  }
                }

                Button {
                  text: "Close"
                  onClicked: root.dismiss()
                }
              }
            }
          }
        }
      }
    }
  }
}
