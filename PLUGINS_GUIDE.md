# PureBit Plugin Development Guide

Welcome to the **PureBit** addon ecosystem. This guide explains how to build, test, and deploy custom audio filters for the PureBit engine.

## 1. Technical Architecture
PureBit processes audio in **blocks of 480 frames** at a **48,000Hz** sample rate. Every plugin is a Python class loaded dynamically at runtime.

## 2. The Core Plugin Template
To create an addon, create a `.py` file in the `/plugins` directory. Your class must follow this strict structure:

```python
import numpy as np

class Plugin:
    def __init__(self):
        # The name shown in the MenuBar and Manager
        self.name = "My Custom Filter"
        # Enable by default?
        self.enabled = True
        # File name is auto-detected
        self.file_name = "my_filter.py"

    def process(self, data):
        """
        data: A NumPy array (float32) of the current audio block.
        Expected return: Processed NumPy array of the same size.
        """
        # Example: Amplify audio by 1.5x
        processed_data = data * 1.5
        return processed_data

    def open_settings(self, parent):
        """
        Called when the user clicks 'Settings' in PureBit.
        'parent' is the main wx.Frame.
        """
        pass
```

## 3. Best Practices for Developers
- Vectorization: Use NumPy vector operations (e.g., data * 0.5) instead of for loops. Real-time audio processing requires high-speed calculations.
- Memory Management: Initialize large buffers (like reverb or delay lines) in __init__, not in process.
- Error Handling: Use try-except blocks inside process to prevent the entire audio engine from crashing.

### 4. Creating UI Settings
If your plugin needs sliders or buttons, use wxPython inside the open_settings method:

```Python

import wx

def open_settings(self, parent):
    dlg = wx.TextEntryDialog(parent, "Enter Gain Value:", "Settings", "1.0")
    if dlg.ShowModal() == wx.ID_OK:
        # Update your internal variables based on user input
        print(f"User set value to: {dlg.GetValue()}")
    dlg.Destroy()
```

## 5. Deployment
Simply place your finished .py file into the /plugins folder. Open Plugins Manager in PureBit and click Refresh to activate your addon.
 
© 2026 Jumping Fridge
