```shell
ssh -v fxw@172.16.1.70
用户名：fxw
密码：wladmin
工程位置：/data2/fxw/deep_enc_dec/fargan_enc_dec_v1
训练环境：conda activate deep_enc_dec
```



## dfnet2训练相关

### （1）训练环境搭建

​		执行以下命令按照dfnet训练依赖的库，具体如下：

```sh
# 创建虚拟环境
conda create --name deep_enc_dec python=3.9.19
# 激活CAGCRN环境
conda activate deep_enc_dec
# 根据requirement.txt安装依赖的库，/data/fxw/code/AI_AEC_NS/CAGCRN_v2目录下
pip install -r requirement.txt -i https://pypi.mirrors.ustc.edu.cn/simple/
```

### （2）码本加fargan声码器

- codec2码本+faragan声码器

  ```shell
  cd /data2/fxw/deep_enc_dec/fargan_enc_dec_v1/src
  # linux_x86编译
  gcc fargan_demo.c lpcnet_enc.c fargan.c fargan_quant.c fargan_freedv.c fargan_data.c freq.c nnet.c  burg.c fargan_pred_4stage_vq.c 4stage_direct_split_indopt_vq.c 4stage_direct_split_vq.c  pitchdnn.c parse_lpcnet_weights.c mbest.c kiss_fft.c lpcnet_tables.c nnet_default.c pitchdnn_data.c pitch.c ./x86/x86_dnn_map.c -I./x86 -I../include -I./ -lm -o fargan_demo -O3 -march=native -funroll-loops -fopenmp
  
  # 测试
  ./fargan_demo -encode_c2 alading_v1.pcm alading_v1_enc_c2.bin # 编码
  ./fargan_demo -decode_c2 alading_v1_enc_c2.bin alading_v1_dec.pcm # 解码
  ```

- rvq+faragan声码器

  - 数据集生成

    ```sh
    # dump_data 特征生成工具，为opus源代码编译，编译时./configure --enable-deep-plc
    cd /data2/fxw/deep_enc_dec/fargan_enc_dec_v1/dump_feature
    
    ./dump_data -train ../../opus/dnn/torch/fargan/tts_speech_negative_16k.sw out_features.f32 out_speech.pcm
    ```

  - 训练与测试

    ```shell
    # 利用小批量数据集训练调试效果，大批量数据集/data2/fxw/deep_enc_dec/fargan_enc_dec_v1/dump_feature/out_speech.pcm与out_features.f32
    
    # 先训练rvq，再加载rvq联合训练fargan
    python ./train_rvq_v2.py ../../dump_feature/mini_data/out_features_mini.f32 \
            ../../dump_feature/mini_data/out_speech_mini.pcm \
            output_dir_rvq \
            --rvq-n-codebooks 2 \
            --rvq-codebook-size 1024 \
            --rvq-codebook-dim 17 \
            --rvq-input-dim 17 \
            --rvq-requires-projection True \
            --rvq-start 1 \
            --epochs 150 --batch-size 4096 --lr 0.002 --cuda-visible-devices 0 > train_rvq_log.txt
    
    # 加载预训练的fargan和rvq模块，进行联合训练
    python ./train_fargan.py \
      ../../dump_feature/mini_data/out_features_mini.f32 \
      ../../dump_feature/mini_data/out_speech_mini.pcm \
      rvq_fargan_output_dir_v1 \
      --rvq-n-codebooks 2 \
      --rvq-codebook-size 1024 \
      --rvq-codebook-dim 18 \
      --rvq-input-dim 18 \
      --pretrained-fargan /data2/fxw/deep_enc_dec/fargan_enc_dec_v1/train_fargan/rvq_fargan_sep/fargan_sq1Ab_adv_50.pth \
      --pretrained-rvq /data2/fxw/deep_enc_dec/fargan_enc_dec_v1/train_fargan/rvq_fargan_sep/output_dir_rvq/checkpoints/rvq_150.pth \
      --epochs 400 --batch-size 4096 --lr 0.002 --cuda-visible-devices 0 > pretrained_rvq_fargan_log_v1.txt
    
    # 对抗训练
    python ./adv_train_fargan.py \
            ../../dump_feature/mini_data/out_features_mini.f32 \
            ../../dump_feature/mini_data/out_speech_mini.pcm \
            rvq_fargan_output_dir_v0 \
            --rvq-n-codebooks 2 \
            --rvq-codebook-size 1024 \
            --rvq-codebook-dim 18 \
            --rvq-input-dim 18 \
            --rvq-requires-projection True \
            --lr 0.000002 --reg-weight 5 --batch-size 128 --cuda-visible-devices 0 \
            --device cuda:1 \
            --initial-checkpoint ./rvq_fargan_output_dir_v1/checkpoints/rvq_fargan_173.pth > adv_train_fargan_log_v0.txt
    
    # 详见/data2/fxw/deep_enc_dec/fargan_enc_dec_v1/train_fargan/rvq_fargan_sep/train.sh脚本
    # 测试详见/data2/fxw/deep_enc_dec/fargan_enc_dec_v1/train_fargan/rvq_fargan_sep/test.sh
    ```
    
    

