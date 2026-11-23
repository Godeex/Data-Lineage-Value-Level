# 复现清单 checklist：AgentDB-261102

## 环境
- [x] OS / 驱动 / CUDA / cuDNN 版本已记录：Linux 6.8.0-138-generic；NVIDIA L40 48G 300W；CUDA/cuDNN 版本待 `nvidia-smi` 与 `nvcc --version` 落盘（P0 首日补）
- [ ] 依赖锁版本：requirements.txt / uv.lock 待 experiment-coding 建仓后生成
- [x] 硬件记录：L40 48G ×1；CPU 实验记核心数（待补）

## 目录脚手架
- [ ] 目录布局待 project-structure `scaffold.py` 生成（Cookiecutter Data Science 布局）
- [x] raw 数据只读不改：约定 `data/raw/` 只读，clean 产物写 `data/clean/`
- [x] 可复用逻辑下沉 `src/`；notebook 只做探索

## 随机种子全覆盖
- [x] `random.seed(s)` + `os.environ["PYTHONHASHSEED"]=str(s)`（进程启动前设）
- [x] NumPy `np.random.default_rng(s)`
- [x] PyTorch `torch.manual_seed(s)` + `torch.cuda.manual_seed_all(s)`（若用本地 LLM 推理）
- [x] cuDNN 确定性：`torch.backends.cudnn.deterministic=True` + `benchmark=False`
- [x] DataLoader worker 种子：`worker_init_fn` + `generator=torch.Generator().manual_seed(s)`
- [x] 多种子用途：5 个 LLM seed 只估计算法随机性；独立脚本 n 另报，不混称

## 配置管理
- [ ] Hydra 分层配置（conf/ model/dataset 分组）待建仓
- [x] 命令行可覆盖，run 自动存最终合成配置

## 数据 / 模型版本（完整档）
- [ ] DVC 跟踪大文件（待建仓；小规模可先 git-lfs/哈希清单）
- [ ] `dvc.yaml` stages + `dvc.lock`（完整档可选）

## 流水线
- [ ] Snakemake/invoke 流水线（完整档可选；当前用 Make + Python 脚本）

## 实验日志
- [ ] MLflow 或 W&B（选型 UNKNOWN，未定；敏感数据用 offline）
- [x] 结果文件命名规范：`results/{exp_id}/{method}/{seed}.json`

## 固定项
- [ ] 数据划分脚本 + 种子：按项目/仓库分组 70/15/15，seed=42（脚本待写）
- [x] 超参/训练策略记录：配置链接待建仓
- [x] 运行命令记录：`python -m src.run --config conf/exp01.yaml --seed 42`
- [x] 同种子两次跑结果一致性的验证步骤已写入实验协议

> 硬验收：别人/未来的你用本清单能复跑出同一个数；未完成项在 P0 首日补齐并回写。
