# server/tts_piper.py
from __future__ import annotations
import subprocess
import tempfile
import os
from pathlib import Path

import asyncio, shlex
import os, subprocess, asyncio
from pathlib import Path


# 模型
DEFAULT_VOICE = "en_US-amy-medium.onnx"

PIPER_DIR = Path(__file__).resolve().parent.parent / "models" / "piper_win64"
PIPER_EXE = PIPER_DIR / "piper.exe"

# 语速：Piper 的 length_scale，<1 加快，>1 变慢，默认 1.0
DEFAULT_LENGTH_SCALE = float(os.getenv("TTS_LENGTH_SCALE", "0.9"))

class PiperTTS:
    def __init__(self, piper_exe: Path = PIPER_EXE, default_voice: str = DEFAULT_VOICE,
                 length_scale: float = DEFAULT_LENGTH_SCALE):
        self.piper_exe = Path(piper_exe)
        if not self.piper_exe.exists():
            raise FileNotFoundError(f"piper.exe not found: {self.piper_exe}")

        self.workdir = self.piper_exe.parent
        # 默认模型文件
        self.default_model = self.workdir / default_voice
        if not self.default_model.exists():
            raise FileNotFoundError(f"piper model not found: {self.default_model}")
        self.length_scale = length_scale

    def _resolve_model(self, model_path: str | Path | None) -> Path:
        """
        解析路径：
        - 传入绝对/相对路径则按给定路径
        - 只传文件名，在 piper.exe 同目录下找
        - 没传，则用默认模型
        """
        if model_path:
            p = Path(model_path)
            if not p.is_absolute():
                p = self.workdir / p.name
        else:
            p = self.default_model

        if not p.exists():
            raise FileNotFoundError(f"voice model not found: {p}")
        return p

    def synth(self, text: str, model_path: str | Path | None = None) -> bytes:
        """
        调用Piper把text合成到WAV临时文件，返回WAV
        """
        model = self._resolve_model(model_path)

        # 创建临时WAV文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_name = tmp.name

        try:
            cmd = [
                str(self.piper_exe),
                "-m", str(model),   # 模型
                "-f", tmp_name,     # 输出WAV文件
                "--length_scale", str(self.length_scale),
            ]

            proc = subprocess.run(
                cmd,
                input=text,
                text=True,
                cwd=str(self.workdir),
                capture_output=True,   
                check=True,
            )

            with open(tmp_name, "rb") as f:
                wav_bytes = f.read()
            return wav_bytes

        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Piper failed (exit {e.returncode}).\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}"
            ) from e
        finally:
            try:
                os.remove(tmp_name)
            except Exception:
                pass

    async def stream_s16le(self, text: str, model_path: str | Path | None = None,
                           sample_rate: int = 16000, chunk_ms: int = 20):
        """
        以裸PCM(s16le, mono)流式输出 Piper 音频。
        在Windows下用 subprocess.Popen + 线程执行阻塞 IO，避免 asyncio.create_subprocess_exec 的 NotImplementedError
        """


        model = Path(self._resolve_model(model_path))
        chunk_bytes = int(sample_rate * (chunk_ms / 1000.0) * 2)

        piper_exe = Path(self.piper_exe)
        piper_dir = str(piper_exe.parent)

        if not piper_exe.exists():
            raise RuntimeError(f"piper.exe not found: {piper_exe}")
        if not model.exists():
            raise RuntimeError(f"voice model not found: {model}")

        args = [
            str(piper_exe),
            "-m", str(model),
            "-f", str(sample_rate),
            "--output-raw",
            "--sentence_silence", "0.25",
            "--length_scale", str(self.length_scale),
        ]
        env = os.environ.copy()
        env["PATH"] = piper_dir + os.pathsep + env.get("PATH", "")

        # Popen阻塞，配合线程池做读写 
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=piper_dir,
            env=env,
        )

        loop = asyncio.get_running_loop()

        async def _gen():
            try:
                # 写入文本并关闭stdin,在线程里执行阻塞写
                def _write_and_close():
                    proc.stdin.write(text.encode("utf-8"))
                    proc.stdin.flush()
                    proc.stdin.close()
                await asyncio.to_thread(_write_and_close)

                # 持续读取stdout每次阻塞 read，用线程搬运到异步
                while True:
                    chunk = await loop.run_in_executor(None, proc.stdout.read, chunk_bytes)
                    if not chunk:
                        break
                    yield chunk

                # 等待进程结束并检查返回码
                rc = await loop.run_in_executor(None, proc.wait)
                if rc != 0:
                    err = await asyncio.to_thread(proc.stderr.read)
                    raise RuntimeError(f"Piper failed (exit {rc}): {err.decode('utf-8','ignore').strip()[:800]}")
            finally:
                try:
                    if proc and proc.poll() is None:
                        proc.kill()
                except Exception:
                    pass

        return _gen()


# 单例，后端直接import
piper_tts = PiperTTS()
