import os
import traceback

import librosa
import numpy as np
import tqdm
from scipy.io import wavfile

from modules.utils import load_audio

from .slicer import Slicer


class PreProcess:
    def __init__(self, sampling_rate, training_dir):
        self.slicer = Slicer(
            sr=sampling_rate,
            threshold=-32,
            min_length=800,
            min_interval=400,
            hop_size=15,
            max_sil_kept=150,
        )
        self.sr = sampling_rate
        self.per = 3.7
        self.overlap = 0.3
        self.tail = self.per + self.overlap
        self.max = 0.95
        self.alpha = 0.8

        self.gt_wavs_dir = os.path.join(training_dir, "0_gt_wavs")
        self.wavs16k_dir = os.path.join(training_dir, "1_16k_wavs")

    def norm_write(self, tmp_audio, idx0, idx1):
        tmp_audio = (tmp_audio / np.abs(tmp_audio).max() * (self.max * self.alpha)) + (
            1 - self.alpha
        ) * tmp_audio
        wavfile.write(
            os.path.join(self.gt_wavs_dir, f"{idx0}_{idx1}.wav"),
            self.sr,
            (tmp_audio * 32768).astype(np.int16),
        )
        tmp_audio = librosa.resample(tmp_audio, orig_sr=self.sr, target_sr=16000)
        wavfile.write(
            os.path.join(self.wavs16k_dir, f"{idx0}_{idx1}.wav"),
            16000,
            (tmp_audio * 32768).astype(np.int16),
        )

    def pipeline(self, path: str, index: int):
        try:
            audio = load_audio(path, self.sr)
            idx1 = 0
            for audio in self.slicer.slice(audio):
                i = 0
                while 1:
                    start = int(self.sr * (self.per - self.overlap) * i)
                    i += 1
                    if len(audio[start:]) > self.tail * self.sr:
                        tmp_audio = audio[start : start + int(self.per * self.sr)]
                        self.norm_write(tmp_audio, index, idx1)
                        idx1 += 1
                    else:
                        tmp_audio = audio[start:]
                        break
                self.norm_write(tmp_audio, index, idx1)
        except:
            print(f"{path}->{traceback.format_exc()}")

    def pipeline_mapping(self, dataset_dir: str, num_processes: int):
        os.makedirs(self.gt_wavs_dir, exist_ok=True)
        os.makedirs(self.wavs16k_dir, exist_ok=True)
        try:
            infos = [
                (os.path.join(dataset_dir, name), index)
                for index, name in enumerate(sorted(list(os.listdir(dataset_dir))))
            ]
            for path, index in tqdm.tqdm(infos):
                self.pipeline(path, index)

            # def task(infos):
            #     for path, index in tqdm.tqdm(infos):
            #         self.pipeline(path, index)

            # with ProcessPoolExecutor() as executor:
            #     for i in range(num_processes):
            #         executor.submit(task, infos[i::num_processes])
        except:
            print(f"Failed {dataset_dir}->{traceback.format_exc()}")


def preprocess_dataset(
    dataset_dir: str,
    sampling_rate: int,
    num_processes: int,
    training_dir: str,
):
    pp = PreProcess(sampling_rate, training_dir)
    if os.path.exists(pp.gt_wavs_dir) and os.path.exists(pp.wavs16k_dir):
        return
    pp.pipeline_mapping(dataset_dir, num_processes)
