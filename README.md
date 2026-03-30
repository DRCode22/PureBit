# PureBit - Professional AI Audio Isolation

PureBit is a specialized real-time audio processing engine developed by **Jumping Fridge** organization. It provides studio-grade noise cancellation and high-fidelity monitoring for Windows users.

## Key Features
* **Deep Learning Noise Reduction:** Powered by the RNNoise library for intelligent voice isolation.
* **Low Latency Monitoring:** Optimized for Windows Multimedia Class Scheduler (Avrt.dll) to minimize delay.
* **Dynamic Plugin Architecture:** Modular system to add custom audio filters on the fly.
* **Pro Audio Tools:** Built-in recording (48kHz WAV), Echo/Reverb effects, and Output Gain control.

## Installation & Setup
1. Clone the repository: `git clone https://github.com/DRCode22/PureBit/`
2. Install dependencies: `pip install -r requirements.txt`
3. Ensure `rnnoise.dll` is present in the root directory.
4. Run the application: `python PureBit.py`

## Credits
* **Lead Developer:** DR.Code (Mohamed Antar)
* **Organization:** Jumping Fridge - [Website](https://jumpingfridge.gt.tc/)
* **Community:** Join our Telegram Channel [UL Tech AR](https://t.me/ultech_ar)

## License
Licensed under the MIT License - See the LICENSE file for details.

---

## Extensibility & Addons
PureBit is designed to be fully extensible. Developers can create custom audio filters, spectral analyzers, or sound effects using Python and NumPy.

> **Are you a developer?** > Check out the [Plugin Development Guide](PLUGINS_GUIDE.md) to learn how to build and integrate your own audio DSP modules into the PureBit engine.

---
### Support & Community
* **Technical Articles:** [Jumping Fridge Portal](https://jumpingfridge.gt.tc/)
* **Developer Updates:** [Jumping frige TelegramChannel ](https://t.me/ultech_ar)
* **Bug Reports:** Please use the [GitHub Issues](https://github.com/DRCode22/PureBit/issues) page.

---
*© 2026 Jumping Fridge
