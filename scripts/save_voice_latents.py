import os
import glob
import sys
sys.path.append('..')
import argparse
from pathlib import Path

import torch
from tortoise.api import TextToSpeech
from tortoise.utils.audio import load_audio, get_voices

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# Tortoise transformer batch size
TRANSFORMER_BATCH_SIZE = 4
# use half precision
USE_HALF = False
USE_DEEPSPEED = True
# Cache KV of transfromer of previous timesteps, this is required for efficient inference
USE_KV_CACHE = True
# Keeping this feature false, where extra inputs can be given in [] brackets
# regarding audio like emotions, expressions etc.
USE_REDACTION = True
SAMPLE_RATE = 22050
current_filepath = os.path.dirname(os.path.abspath(__file__))
TORTOISE_CKPT_DIR = os.path.join(Path(current_filepath).parent.parent, "checkpoints")

def parse_args():
    parser = argparse.ArgumentParser(description="save default voice latents")
    parser.add_argument(
        "-i", "--input-dir", dest="input_dir", default="../tortoise/voices",
        help="Path to the dir containing dir for each speaker containing wavs"
    )
    parser.add_argument(
        "-o", "--output-dir", dest="output_dir", default="../tortoise/voice_latents",
        help="Path to the dir to save speaker latents"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    
    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)
        
    tts = TextToSpeech(
        models_dir=TORTOISE_CKPT_DIR, use_deepspeed=USE_DEEPSPEED, 
        kv_cache=USE_KV_CACHE, half=USE_HALF, device=DEVICE, 
        enable_redaction=USE_REDACTION, 
        autoregressive_batch_size=TRANSFORMER_BATCH_SIZE
    )
        
    speaker_dirs = [os.path.join(args.input_dir, d_) for d_ in os.listdir(args.input_dir)]
    
    for speaker_dir in speaker_dirs:
        speaker_name = os.path.basename(speaker_dir)
        print("> Processing ", speaker_name)
        audio_files = glob.glob(os.path.join(speaker_dir, "*.wav")) + \
                 glob.glob(os.path.join(speaker_dir, "*.mp3"))
        audios = [load_audio(audio_file, SAMPLE_RATE) for audio_file in audio_files]
        
        if len(audios) == 0:
            print(">  Skipping {} as no audio files found".format(speaker_dir))
            continue
        
        conditioning_latents = tts.get_conditioning_latents(audios)
        
        save_dir = os.path.join(args.output_dir, speaker_name)
        os.mkdir(save_dir)
        save_path = os.path.join(save_dir, speaker_name + ".pth")
        
        torch.save(conditioning_latents, save_path)
    


if __name__ == '__main__':
    main()