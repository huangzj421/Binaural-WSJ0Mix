import os
import numpy as np
import pandas as pd
import argparse
from utils import wavwrite, read_scaled_wav, fix_length, convolve_hrtf_reverb
from urllib.request import urlretrieve
import zipfile


def create_binaural_wsj0mix(wsj_root, output_root,
                                  datafreqs=['8k','16k'], datamodes=['min','max']):

    S1_DIR = 's1'
    S2_DIR = 's2'
    MIX_DIR = 'mix'
    pypath = os.path.dirname(__file__)
    FILELIST_STUB = os.path.join(pypath, 'metadata', 'mix_2_spk_filenames_{}.csv')
    BINAU = True  # Generate binaural audio
    hrtf_root = os.path.join(output_root, 'hrtfdata')
    os.makedirs(hrtf_root, exist_ok=True)

    scaling_npz_stub = os.path.join(pypath, 'metadata', 'scaling_{}.npz')
    hrtf_meta_stub = os.path.join(pypath, 'metadata', 'hrtf_reverb_meta_{}.csv')
    
    hrtf_wav_path = os.path.join(hrtf_root, 'CATT_RIRs', 'Binaural', '16k')

    def reporthook(blocknum, blocksize, totalsize):
        print(
            "\rdownloading: %5.1f%%" % (100.0 * blocknum * blocksize / totalsize),
            end="",
        )

    if not os.path.exists(hrtf_wav_path):

        print("Download CATT_RIRs dataset into %s" % hrtf_root)
        urlretrieve(
            "https://iosr.uk/software/downloads/CATT_RIRs.zip",
            os.path.join(hrtf_root, "CATT_RIRs.zip"),
            reporthook=reporthook,
        )
        file = zipfile.ZipFile(os.path.join(hrtf_root, "CATT_RIRs.zip"))
        file.extractall(path=hrtf_root)
        os.remove(os.path.join(hrtf_root, "CATT_RIRs.zip"))

    for sr_str in datafreqs:
        wav_dir = 'wav' + sr_str
        if sr_str == '8k':
            sr = 8000
            downsample = True
        else:
            sr = 16000
            downsample = False

        for datalen_dir in datamodes:
            for splt in ['tt','cv','tr']:
                output_path = os.path.join(output_root, wav_dir, datalen_dir, splt)

                s1_output_dir = os.path.join(output_path, S1_DIR)
                os.makedirs(s1_output_dir, exist_ok=True)
                s2_output_dir = os.path.join(output_path, S2_DIR)
                os.makedirs(s2_output_dir, exist_ok=True)
                mix_output_dir = os.path.join(output_path, MIX_DIR)
                os.makedirs(mix_output_dir, exist_ok=True)

                print('{} {} dataset, {} split'.format(wav_dir, datalen_dir, splt))

                # read filenames
                wsjmix_path = FILELIST_STUB.format(splt)
                wsjmix_df = pd.read_csv(wsjmix_path)
                # read scaling file
                scaling_path = scaling_npz_stub.format(splt)
                scaling_npz = np.load(scaling_path, allow_pickle=True)
                wsjmix_key = 'scaling_wsjmix_{}_{}'.format(sr_str, datalen_dir)
                scaling_mat = scaling_npz[wsjmix_key]

                hrtf_meta_path = hrtf_meta_stub.format(splt)
                hrtf_df = pd.read_csv(hrtf_meta_path)

                for i_utt, (output_name, s1_path, s2_path) in enumerate(wsjmix_df.itertuples(index=False, name=None)):

                    s1 = read_scaled_wav(os.path.join(wsj_root, s1_path), scaling_mat[i_utt][0], downsample)
                    s2 = read_scaled_wav(os.path.join(wsj_root, s2_path), scaling_mat[i_utt][1], downsample)

                    s1, s2 = fix_length(s1, s2, datalen_dir)

                    # apply hrtf to binaural channels
                    if BINAU:
                        s1, s2, output_name = convolve_hrtf_reverb([s1, s2], hrtf_wav_path, hrtf_df, output_name, sr)

                    mix = s1 + s2
                    wavwrite(os.path.join(mix_output_dir, output_name), mix, sr)
                    wavwrite(os.path.join(s1_output_dir, output_name), s1, sr)
                    wavwrite(os.path.join(s2_output_dir, output_name), s2, sr)

                    if (i_utt + 1) % 500 == 0:
                        print('Completed {} of {} utterances'.format(i_utt + 1, len(wsjmix_df)))



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--wsj0-root', type=str,
                        help='Path to the folder containing wsj0/')
    parser.add_argument('--output-dir', type=str,
                        help='Output directory for writing binaural wsj0-2mix with reverberation.')
    args = parser.parse_args()
    create_binaural_wsj0mix(args.wsj0_root, args.output_dir)
