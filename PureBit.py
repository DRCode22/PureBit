import wx
import sounddevice as sd
import numpy as np
import ctypes
import os
import soundfile as sf
import keyboard
import webbrowser
from datetime import datetime
import importlib

from PluginNG import PluginManager

class AudioEngine:
    def __init__(self):
        self.model = None
        self.stream = None
        self.is_running = False
        self.reduction_level = 1.0
        self.gain_db = 0.0
        self.reverb_on = False
        self.reverb_level = 0.4
        self.reverb_buffer = np.zeros(4800)
        self.is_recording = False
        self.recorded_frames = []
        self.current_gain = 1.0
        self.gate_threshold = 0.004
        self.fade_speed = 0.12
        
        self.plugin_manager = PluginManager()

        base_path = os.path.dirname(os.path.abspath(__file__))
        dll_path = os.path.join(base_path, "rnnoise.dll")
        try:
            self.lib = ctypes.CDLL(dll_path, winmode=0)
            self.lib.rnnoise_create.restype = ctypes.c_void_p
            self.lib.rnnoise_process_frame.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]
            self.model = self.lib.rnnoise_create(None)
        except: print("⚠️ RNNoise DLL missing")

    def apply_reverb(self, data):
        decay = 0.35
        self.reverb_buffer = np.roll(self.reverb_buffer, -len(data))
        self.reverb_buffer[-len(data):] = data + self.reverb_buffer[:len(data)] * decay
        return data + self.reverb_buffer[-len(data):] * self.reverb_level

    def audio_callback(self, indata, outdata, frames, time, status):
        if self.is_running:
            raw_input = indata[:, 0].copy().astype(np.float32)
            input_mono = (raw_input * 32768.0).astype(np.float32)
            in_ptr = input_mono.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            out_ptr = (ctypes.c_float * 480)()
            
            self.lib.rnnoise_process_frame(self.model, out_ptr, in_ptr)
            denoised = np.array(out_ptr) / 32768.0
            
            mixed = (denoised * self.reduction_level) + (raw_input * (1.0 - self.reduction_level))
            rms = np.sqrt(np.mean(mixed**2))
            target_gate = 1.0 if rms > self.gate_threshold else 0.0
            self.current_gain += (target_gate - self.current_gain) * self.fade_speed
            
            processed = mixed * self.current_gain
            processed = self.plugin_manager.run_plugins(processed)
            
            if self.reverb_on:
                processed = self.apply_reverb(processed)
                
            gain_factor = 10 ** (self.gain_db / 20)
            final_output = np.clip(processed * gain_factor, -0.99, 0.99)
            
            if self.is_recording:
                self.recorded_frames.append(final_output.copy())
            
            outdata[:] = final_output.reshape(-1, 1)

    def start(self, in_id, out_id):
        self.stream = sd.Stream(device=(in_id, out_id), samplerate=48000, blocksize=480,
                                dtype='float32', channels=1, callback=self.audio_callback)
        self.stream.start()
        self.is_running = True

    def stop(self):
        self.is_running = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

class PureBit(wx.Frame):
    def __init__(self):
        super().__init__(None, title='PureBit', size=(500, 750))
        self.engine = AudioEngine()
        
        self.undo_stack = []
        self.redo_stack = []
        
        devs = sd.query_devices()
        self.in_list = [(i, d['name']) for i, d in enumerate(devs) if d['max_input_channels'] > 0]
        self.out_list = [(i, d['name']) for i, d in enumerate(devs) if d['max_output_channels'] > 0]
        
        self.init_ui()
        self.create_menubar()
        self.setup_hotkeys()

    def create_menubar(self):
        menubar = wx.MenuBar()

        edit_menu = wx.Menu()
        undo_item = edit_menu.Append(wx.ID_UNDO, "Undo (Toggle Filter)\tCtrl+Z")
        redo_item = edit_menu.Append(wx.ID_REDO, "Redo\tCtrl+Y")
        edit_menu.AppendSeparator()
        edit_menu.Append(wx.ID_ANY, "Clear Recording History").Enable(False)
        
        self.Bind(wx.EVT_MENU, self.on_undo, undo_item)
        self.Bind(wx.EVT_MENU, self.on_redo, redo_item)
        menubar.Append(edit_menu, "&Edit")

        self.effects_menu = wx.Menu()
        self.update_effects_menu()
        menubar.Append(self.effects_menu, "&Effects")

        about_menu = wx.Menu()
        about_app = about_menu.Append(wx.ID_ANY, "About App")
        user_guide = about_menu.Append(wx.ID_ANY, "User Guide")
        addons_guide = about_menu.Append(wx.ID_ANY, "Addons Guide")
        app_repo = about_menu.Append(wx.ID_ANY, "App Repository")
        
        about_menu.AppendSeparator()
        
        dev_menu = wx.Menu()
        jf_web = dev_menu.Append(wx.ID_ANY, "Jumping Fridge Website")
        tg_chan = dev_menu.Append(wx.ID_ANY, "Telegram Channel")
        about_menu.AppendSubMenu(dev_menu, "Developer")

        self.Bind(wx.EVT_MENU, lambda e: self.open_local_html("AboutApp.html"), about_app)
        self.Bind(wx.EVT_MENU, lambda e: self.open_local_html("Userguide.html"), user_guide)
        self.Bind(wx.EVT_MENU, lambda e: self.open_local_html("AddonsGuide.html"), addons_guide)
        self.Bind(wx.EVT_MENU, lambda e: webbrowser.open("https://github.com/DRCode22/PureBit/"), app_repo)
        self.Bind(wx.EVT_MENU, lambda e: webbrowser.open("https://jumpingfridge.gt.tc/"), jf_web)
        self.Bind(wx.EVT_MENU, lambda e: webbrowser.open("https://t.me/ultech_ar"), tg_chan)

        menubar.Append(about_menu, "&About")
        self.SetMenuBar(menubar)

    def update_effects_menu(self):
        """تحديث قائمة Effects ديناميكياً لتفعيل/إلغاء الفلاتر"""
        for item in self.effects_menu.GetMenuItems():
            self.effects_menu.Remove(item)
            
        active_plugins = self.engine.plugin_manager.loaded_plugins
        if not active_plugins:
            self.effects_menu.Append(wx.ID_ANY, "No Plugins Found").Enable(False)
        else:
            for plugin in active_plugins:
                label = f"Toggle: {plugin.name}"
                item = self.effects_menu.AppendCheckItem(wx.ID_ANY, label)
                item.Check(plugin.enabled)
                self.Bind(wx.EVT_MENU, lambda evt, p=plugin: self.on_toggle_plugin_state(p), item)
                
                set_item = self.effects_menu.Append(wx.ID_ANY, f"  └─ {plugin.name} Settings")
                self.Bind(wx.EVT_MENU, lambda evt, p=plugin: p.open_settings(self), set_item)
                self.effects_menu.AppendSeparator()

    def on_toggle_plugin_state(self, plugin):
        self.undo_stack.append((plugin, plugin.enabled))
        self.redo_stack.clear()
        
        plugin.enabled = not plugin.enabled
        self.update_effects_menu()
        print(f"🔄 Filter '{plugin.name}' is now {'Enabled' if plugin.enabled else 'Disabled'}")

    def on_undo(self, e):
        if self.undo_stack:
            plugin, prev_state = self.undo_stack.pop()
            self.redo_stack.append((plugin, plugin.enabled))
            plugin.enabled = prev_state
            self.update_effects_menu()

    def on_redo(self, e):
        if self.redo_stack:
            plugin, next_state = self.redo_stack.pop()
            self.undo_stack.append((plugin, plugin.enabled))
            plugin.enabled = next_state
            self.update_effects_menu()

    def open_local_html(self, filename):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if os.path.exists(path):
            webbrowser.open(f"file:///{path}")
        else:
            wx.MessageBox(f"File not found: {filename}", "Error", wx.ICON_ERROR)

    def init_ui(self):
        panel = wx.Panel(self)
        self.main_vbox = wx.BoxSizer(wx.VERTICAL)
        panel.SetBackgroundColour('#F0F4F8')

        header = wx.StaticText(panel, label="PUREBIT")
        header.SetFont(wx.Font(22, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.main_vbox.Add(header, 0, wx.ALL | wx.CENTER, 20)

        self.create_section_label(panel, "Input Microphone:")
        self.in_cb = wx.ComboBox(panel, choices=[d[1] for d in self.in_list], style=wx.CB_READONLY, name="Input Microphone")
        self.main_vbox.Add(self.in_cb, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 15)

        self.create_section_label(panel, "Output Monitor:")
        self.out_cb = wx.ComboBox(panel, choices=[d[1] for d in self.out_list], style=wx.CB_READONLY, name="Output Monitor")
        self.main_vbox.Add(self.out_cb, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 15)

        self.sld_red = self.create_slider(panel, "AI Noise Reduction Strength", 100)
        self.sld_gain = self.create_slider(panel, "Output Volume Gain", 0, -10, 20)

        self.main_vbox.Add(wx.StaticLine(panel), 0, wx.EXPAND|wx.ALL, 10)
        
        rev_h_box = wx.BoxSizer(wx.HORIZONTAL)
        self.rev_check = wx.CheckBox(panel, label="Enable Echo (F1)")
        self.rev_check.Bind(wx.EVT_CHECKBOX, self.on_reverb_check)
        rev_h_box.Add(self.rev_check, 0, wx.LEFT|wx.ALIGN_CENTER_VERTICAL, 15)
        
        self.rev_toggle_btn = wx.Button(panel, label="Echo settings", size=(120, 30))
        self.rev_toggle_btn.Bind(wx.EVT_BUTTON, self.on_toggle_rev_panel)
        rev_h_box.AddStretchSpacer()
        rev_h_box.Add(self.rev_toggle_btn, 0, wx.RIGHT, 15)
        self.main_vbox.Add(rev_h_box, 0, wx.EXPAND|wx.BOTTOM, 10)

        self.rev_panel = wx.Panel(panel)
        self.rev_panel.SetBackgroundColour('#E1E8ED')
        rev_p_vbox = wx.BoxSizer(wx.VERTICAL)
        self.sld_rev_lvl = wx.Slider(self.rev_panel, value=40, minValue=0, maxValue=100, name="Echo Intensity Slider")
        self.sld_rev_lvl.Bind(wx.EVT_SLIDER, self.on_rev_lvl_change)
        rev_p_vbox.Add(wx.StaticText(self.rev_panel, label="Echo intensity:"), 0, wx.LEFT|wx.TOP, 5)
        rev_p_vbox.Add(self.sld_rev_lvl, 0, wx.EXPAND|wx.ALL, 5)
        self.rev_panel.SetSizer(rev_p_vbox)
        self.rev_panel.Hide()
        self.main_vbox.Add(self.rev_panel, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 15)

        self.main_vbox.Add(wx.StaticLine(panel), 0, wx.EXPAND|wx.ALL, 10)

        rec_box = wx.BoxSizer(wx.HORIZONTAL)
        self.rec_btn = wx.Button(panel, label="Start recording", size=(150, 45))
        self.rec_btn.Bind(wx.EVT_BUTTON, self.on_record_click)
        
        self.save_btn = wx.Button(panel, label="Save Recording", size=(150, 45))
        self.save_btn.SetBackgroundColour('#FFC107')
        self.save_btn.Hide()
        self.save_btn.Bind(wx.EVT_BUTTON, self.on_save_click)
        
        rec_box.Add(self.rec_btn, 1, wx.LEFT|wx.RIGHT, 10)
        rec_box.Add(self.save_btn, 1, wx.LEFT|wx.RIGHT, 10)
        self.main_vbox.Add(rec_box, 0, wx.EXPAND|wx.BOTTOM, 15)

        effects_btn_box = wx.BoxSizer(wx.HORIZONTAL)
        
        self.plug_btn = wx.Button(panel, label="Plugins Manager", size=(-1, 45))
        self.plug_btn.SetBackgroundColour('#34495E')
        self.plug_btn.SetForegroundColour('white')
        self.plug_btn.Bind(wx.EVT_BUTTON, self.on_open_plugins)
        
        effects_btn_box.Add(self.plug_btn, 1, wx.EXPAND, 0)
        self.main_vbox.Add(effects_btn_box, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 15)

        self.btn_main = wx.Button(panel, label="START AUDIO ENGINE", size=(-1, 65))
        self.btn_main.SetBackgroundColour('#2ECC71')
        self.btn_main.SetForegroundColour('white')
        self.btn_main.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.btn_main.Bind(wx.EVT_BUTTON, self.on_main_toggle)
        self.main_vbox.Add(self.btn_main, 0, wx.EXPAND|wx.ALL, 15)

        panel.SetSizer(self.main_vbox)
        self.Layout()

    def create_section_label(self, p, text):
        lbl = wx.StaticText(p, label=text)
        lbl.SetForegroundColour('#546E7A')
        self.main_vbox.Add(lbl, 0, wx.LEFT|wx.TOP, 10)

    def create_slider(self, p, label, def_val, min_v=0, max_v=100):
        lbl = wx.StaticText(p, label=f"{label}: {def_val}")
        self.main_vbox.Add(lbl, 0, wx.LEFT|wx.TOP, 10)
        sld = wx.Slider(p, value=def_val, minValue=min_v, maxValue=max_v, name=label)
        sld.Bind(wx.EVT_SLIDER, lambda e: self.on_slider_move(e, lbl, label))
        self.main_vbox.Add(sld, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 15)
        return sld

    def on_slider_move(self, e, lbl, name):
        v = e.GetEventObject().GetValue()
        lbl.SetLabel(f"{name}: {v}")
        if "Reduction" in name: self.engine.reduction_level = v/100.0
        else: self.engine.gain_db = float(v)

    def on_reverb_check(self, e):
        self.engine.reverb_on = self.rev_check.IsChecked()

    def on_toggle_rev_panel(self, e):
        if self.rev_panel.IsShown():
            self.rev_panel.Hide()
            self.rev_toggle_btn.SetLabel("Echo settings")
        else:
            self.rev_panel.Show()
            self.rev_toggle_btn.SetLabel("Hide settings")
        self.Layout()

    def on_rev_lvl_change(self, e):
        self.engine.reverb_level = self.sld_rev_lvl.GetValue() / 100.0

    def on_open_plugins(self, e):
        from PluginNG import PluginManagerDialog
        dlg = PluginManagerDialog(self, self.engine.plugin_manager)
        dlg.ShowModal()
        dlg.Destroy()
        self.update_effects_menu()

    def on_record_click(self, e):
        self.toggle_record_logic()

    def on_save_click(self, e):
        if not self.engine.recorded_frames: return
        with wx.FileDialog(self, "Save File", wildcard="WAV files (*.wav)|*.wav",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL: return
            path = fileDialog.GetPath()
            full_data = np.concatenate(self.engine.recorded_frames)
            sf.write(path, full_data, 48000)
            self.save_btn.Hide()
            self.Layout()

    def toggle_record_logic(self):
        if not self.engine.is_recording:
            self.engine.recorded_frames = []
            self.engine.is_recording = True
            self.rec_btn.SetLabel("Stop recording")
            self.rec_btn.SetBackgroundColour('#FFEB3B')
            self.save_btn.Hide()
        else:
            self.engine.is_recording = False
            self.rec_btn.SetLabel("Start recording")
            self.rec_btn.SetBackgroundColour('#FFFFFF')
            if self.engine.recorded_frames:
                self.save_btn.Show()
        self.Layout()

    def setup_hotkeys(self):
        keyboard.add_hotkey('f1', self.global_reverb_toggle)
        keyboard.add_hotkey('ctrl+r', self.global_record_toggle)

    def global_reverb_toggle(self):
        wx.CallAfter(self.rev_check.SetValue, not self.rev_check.IsChecked())
        self.engine.reverb_on = not self.engine.reverb_on

    def global_record_toggle(self):
        wx.CallAfter(self.toggle_record_logic)

    def on_main_toggle(self, e):
        if not self.engine.is_running:
            i, o = self.in_cb.GetSelection(), self.out_cb.GetSelection()
            if i == -1 or o == -1: return
            self.engine.start(self.in_list[i][0], self.out_list[o][0])
            self.btn_main.SetLabel("STOP ENGINE")
            self.btn_main.SetBackgroundColour('#E74C3C')
        else:
            self.engine.stop()
            self.btn_main.SetLabel("START AUDIO ENGINE")
            self.btn_main.SetBackgroundColour('#2ECC71')

if __name__ == '__main__':
    app = wx.App()
    PureBit().Show()
    app.MainLoop()