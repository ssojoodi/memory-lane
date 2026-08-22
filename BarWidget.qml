import QtQuick
import qs.Ui

BarWidget {
  id: root
  moduleName: "sojoodi.memory-lane"
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰋩"
    fontFamily: "Symbols Nerd Font Mono"
    horizontalMargin: 7.5
    tooltipText: "Memory Lane"
    onPressed: function(mouseButton) {
      if (root.bar && mouseButton === Qt.LeftButton)
        root.bar.run("omarchy-shell shell toggle sojoodi.memory-lane '{}'")
    }
  }
}
