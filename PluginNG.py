import os
import importlib.util
import wx
import numpy as np
import json

class PluginManager:
    def __init__(self):
        self.plugins_folder = os.path.join(os.path.dirname(__file__), "plugins")
        self.settings_file = os.path.join(os.path.dirname(__file__), "settings.json")
        
        if not os.path.exists(self.plugins_folder):
            os.makedirs(self.plugins_folder)
        
        self.loaded_plugins = []
        self.refresh_plugins()

    def load_saved_states(self):

        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    return json.load(f).get("plugin_states", {})
            except:
                return {}
        return {}

    def save_current_states(self):

        states = {p.file_name: p.enabled for p in self.loaded_plugins}
        data = {"plugin_states": states}
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def refresh_plugins(self):
        saved_states = self.load_saved_states()
        self.loaded_plugins = []
        
        for filename in os.listdir(self.plugins_folder):
            if filename.endswith(".py") and filename != "__init__.py":
                try:
                    path = os.path.join(self.plugins_folder, filename)
                    spec = importlib.util.spec_from_file_location(filename[:-3], path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, "Plugin"):
                        instance = module.Plugin()
                        instance.file_name = filename

                        instance.enabled = saved_states.get(filename, False)
                        self.loaded_plugins.append(instance)
                except Exception as e:
                    print(f"Error loading {filename}: {e}")

    def run_plugins(self, audio_data):
        for plugin in self.loaded_plugins:
            if plugin.enabled:
                try:
                    audio_data = plugin.process(audio_data.copy())
                except Exception as e:
                    print(f"Plugin {plugin.file_name} crashed: {e}")
        return audio_data

class PluginManagerDialog(wx.Dialog):
    def __init__(self, parent, manager):
        super().__init__(parent, title="Plugins Manager", size=(450, 400))
        self.manager = manager
        
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        self.list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.list.InsertColumn(0, "Plugin Name", width=200)
        self.list.InsertColumn(1, "Status", width=100)
        
        self.update_list()
        
        vbox.Add(self.list, 1, wx.EXPAND | wx.ALL, 10)
        
        btn_hbox = wx.BoxSizer(wx.HORIZONTAL)
        
        self.toggle_btn = wx.Button(panel, label="Enable/Disable")
        self.toggle_btn.Bind(wx.EVT_BUTTON, self.on_toggle)
        
        self.refresh_btn = wx.Button(panel, label="Refresh Folder")
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        
        self.close_btn = wx.Button(panel, label="Close")
        self.close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))
        
        btn_hbox.Add(self.toggle_btn, 1, wx.ALL, 5)
        btn_hbox.Add(self.refresh_btn, 1, wx.ALL, 5)
        btn_hbox.Add(self.close_btn, 1, wx.ALL, 5)
        
        vbox.Add(btn_hbox, 0, wx.EXPAND | wx.BOTTOM, 10)
        
        panel.SetSizer(vbox)

    def update_list(self):
        self.list.DeleteAllItems()
        for idx, p in enumerate(self.manager.loaded_plugins):
            self.list.InsertItem(idx, p.name)
            status = "Active" if p.enabled else "Disabled"
            self.list.SetItem(idx, 1, status)

    def on_toggle(self, e):
        idx = self.list.GetFirstSelected()
        if idx != -1:
            plugin = self.manager.loaded_plugins[idx]
            plugin.enabled = not plugin.enabled
            self.update_list()

            self.manager.save_current_states()

    def on_refresh(self, e):
        self.manager.refresh_plugins()
        self.update_list()