import io
import unittest
import wave


class AudioDependencyTests(unittest.TestCase):
    def test_whisper_decoder_accepts_real_wave_bytes_with_pinned_pyav(self):
        # Characterizes the upstream API incompatibility observed with PyAV 19.
        from faster_whisper.audio import decode_audio
        fixture = io.BytesIO()
        with wave.open(fixture, 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b'\0\0' * 1600)
        fixture.seek(0)
        samples = decode_audio(fixture)
        self.assertEqual(len(samples), 1600)
        self.assertEqual(float(samples.max()), 0.0)


if __name__ == '__main__': unittest.main()
