/**
 * recorder.js — microphone recording with client-side WAV encoding.
 *
 * Uses the Web Audio API to capture raw PCM audio and encodes it to a
 * 16 kHz mono 16-bit WAV Blob, which is what the Sarvam Speech-to-Text
 * API expects. No external libraries needed.
 */

const VoiceRecorder = (() => {
  const TARGET_RATE = 16000;

  let audioContext = null;
  let mediaStream = null;
  let scriptNode = null;
  let sourceNode = null;
  let chunks = [];
  let recording = false;

  async function start() {
    if (recording) return;
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioContext = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: TARGET_RATE,
    });
    sourceNode = audioContext.createMediaStreamSource(mediaStream);
    scriptNode = audioContext.createScriptProcessor(4096, 1, 1);

    chunks = [];
    scriptNode.onaudioprocess = (e) => {
      if (!recording) return;
      chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    };

    // Route through a zero-gain destination so no sound plays out loud.
    const silentGain = audioContext.createGain();
    silentGain.gain.value = 0;
    scriptNode.connect(silentGain);
    silentGain.connect(audioContext.destination);
    sourceNode.connect(scriptNode);

    recording = true;
  }

  async function stop() {
    if (!recording) return null;
    recording = false;

    // Let the last buffer settle before tearing down.
    await new Promise((r) => setTimeout(r, 200));

    sourceNode.disconnect();
    scriptNode.disconnect();
    mediaStream.getTracks().forEach((t) => t.stop());
    await audioContext.close();

    const length = chunks.reduce((n, c) => n + c.length, 0);
    const pcm = new Float32Array(length);
    let offset = 0;
    for (const c of chunks) { pcm.set(c, offset); offset += c.length; }
    chunks = [];

    if (!length) return null;
    return encodeWav(pcm, audioContext.sampleRate || TARGET_RATE);
  }

  function encodeWav(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    const writeStr = (pos, s) => {
      for (let i = 0; i < s.length; i++) view.setUint8(pos + i, s.charCodeAt(i));
    };

    writeStr(0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    writeStr(8, "WAVE");
    writeStr(12, "fmt ");
    view.setUint32(16, 16, true);          // PCM chunk size
    view.setUint16(20, 1, true);            // PCM format
    view.setUint16(22, 1, true);            // mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);   // byte rate
    view.setUint16(32, 2, true);            // block align
    view.setUint16(34, 16, true);           // bits per sample
    writeStr(36, "data");
    view.setUint32(40, samples.length * 2, true);

    let pos = 44;
    for (let i = 0; i < samples.length; i++, pos += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(pos, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }

    return new Blob([view], { type: "audio/wav" });
  }

  return { start, stop, isRecording: () => recording };
})();
