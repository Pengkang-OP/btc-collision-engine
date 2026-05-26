# BTC碰撞引擎 - 工作流程详细图

> **版本**: v1.2.0 | **最后更新**: 2026-04-21  
> **面向**: 开发者

本文档包含系统各个关键流程的详细序列图和说明。

---

## 目录

1. [系统整体架构](#1-系统整体架构)

2. [启动流程](#2-启动流程)

3. [碰撞模式流程](#3-碰撞模式流程)

4. [地址生成流程](#4-地址生成流程)

5. [GUI交互流程](#5-gui交互流程)

6. [断点管理流程](#6-断点管理流程)

7. [程序运行完整流程](#7-程序运行完整流程)

---

## 1. 系统整体架构

**图1.1**: 三层系统架构（Mermaid graph TD）

```mermaid
graph TD
    subgraph UI["🖥️ 用户界面层 User Interface Layer"]
        CLI["CLI界面<br/>命令行交互"]
        GUI["GUI界面<br/>Tkinter图形界面"]
        API["API接口<br/>可编程调用"]
    end
    
    subgraph Engine["⚙️ 碰撞引擎层 Collision Engine Layer"]
        KCE["KeyCollisionEngine<br/>私钥碰撞引擎"]
        RS["random_search<br/>随机碰撞"]
        RScan["range_scan<br/>范围扫描"]
        BF["brute_force<br/>暴力穷举"]
        
        CS["CollisionStats<br/>统计管理"]
        CM["CheckpointMgr<br/>断点管理"]
        DF["DedupFilter<br/>去重过滤"]
    end
    
    subgraph Core["🧮 核心算法层 Core Algorithm Layer"]
        CBM["CryptoBackendManager<br/>加密后端管理器"]
        PP["PurePython<br/>纯Python实现"]
        OS["OpenSSL<br/>cryptography库"]
        CC["coincurve<br/>libsecp256k1"]
        EC["ecdsa<br/>ecdsa库"]
        
        SC["secp256k1<br/>椭圆曲线运算"]
        HU["hash_utils<br/>哈希工具"]
        B58["base58<br/>Base58编码"]
        WIF["wif<br/>WIF编解码"]
        PAG["P2PKHAddressGenerator<br/>地址生成器"]
    end
    
    CLI --> KCE
    GUI --> KCE
    API --> KCE
    
    KCE --> RS
    KCE --> RScan
    KCE --> BF
    
    KCE --> CS
    KCE --> CM
    KCE --> DF
    KCE --> PM
    
    KCE --> CBM
    CBM --> PP
    CBM --> OS
    CBM --> CC
    CBM --> EC
    
    CBM --> SC
    CBM --> HU
    CBM --> B58
    B58 --> WIF
    CBM --> PAG
    
    style UI fill:#e1f5ff
    style Engine fill:#fff3e0
    style Core fill:#e8f5e9

```python

**说明**:

- **用户界面层**：提供CLI、GUI、API三种交互方式

- **碰撞引擎层**：核心业务逻辑，包含三种碰撞模式和四个管理组件

- **核心算法层**：密码学基础，支持四种加密后端和完整地址生成流程

---

## 2. 启动流程

### 2.1 CLI启动流程

**图2.1**: CLI启动序列图（Mermaid sequenceDiagram）

```mermaid
sequenceDiagram
    participant User as 用户
    participant CLI as CLI Main
    participant Parser as Argument Parser
    participant Resolver as TargetResolver
    participant Engine as KeyCollisionEngine
    
    User->>CLI: 执行命令<br/>python key_collision_cli.py
    CLI->>Parser: 解析参数<br/>parse_args()
    Parser-->>CLI: 返回Namespace对象
    
    CLI->>CLI: 验证参数<br/>mode, targets, options
    CLI->>Resolver: 加载目标地址<br/>load_targets()
    Resolver-->>CLI: 返回目标集合<br/>Set[str]
    
    CLI->>Engine: 创建碰撞引擎<br/>KeyCollisionEngine(targets)
    Note over CLI,Engine: 初始化CheckpointManager<br/>DeduplicationFilter<br/>DataLogger
    Engine-->>CLI: 引擎就绪
    
    CLI->>Engine: 启动引擎<br/>start(mode, **kwargs)
    Note over CLI,Engine: 后台线程启动<br/>random_search/range_scan/brute_force
    Engine-->>CLI: 运行中...
    
    loop 每0.5秒进度回调
        Engine->>CLI: on_progress(stats)
        CLI->>User: 显示进度<br/>速度/已检查/匹配数
    end

```python

**启动步骤说明**:

1. **参数解析**：使用argparse解析命令行参数

2. **参数验证**：检查mode、targets、start/end等参数有效性

3. **目标加载**：从文件或命令行参数加载目标地址集合

4. **引擎创建**：初始化KeyCollisionEngine及其组件

5. **引擎启动**：在后台线程启动碰撞检测

6. **进度回调**：每0.5秒更新一次进度显示

### 2.2 GUI启动流程

**图2.2**: GUI启动序列图（Mermaid sequenceDiagram）

```mermaid
sequenceDiagram
    participant User as 用户
    participant Main as Python Main
    participant GUI as CollisionGUI
    participant Input as TargetInput
    participant Control as ControlPanel
    
    User->>Main: 运行程序<br/>python key_collision_gui.py
    Main->>GUI: 创建Tk根窗口<br/>tk.Tk()
    GUI->>GUI: 设置窗口属性<br/>title, geometry, theme
    
    GUI->>Input: 创建目标输入组件
    Input-->>GUI: 组件创建完成
    
    GUI->>Control: 创建控制面板
    Control-->>GUI: 组件创建完成
    
    GUI->>GUI: 创建其他组件<br/>进度显示/日志/统计
    GUI-->>Main: 初始化完成
    
    Main->>User: 显示窗口<br/>mainloop()
    User-->>Main: 界面就绪

```python

**GUI启动特点**:

- 使用Tkinter创建图形界面

- 多标签页设计：单地址生成、批量生成、碰撞检测、地址验证

- 事件驱动的交互模式

- 后台线程执行碰撞任务，避免UI阻塞

---

## 3. 碰撞模式流程

### 3.1 随机碰撞模式

**图3.1**: 随机碰撞序列图（Mermaid sequenceDiagram）

```mermaid
sequenceDiagram
    participant Engine as Engine
    participant Pool as ThreadPool Executor
    participant Worker as Worker Thread
    participant Dedup as Dedup Filter
    participant KeyMgr as SecureKeyManager
    participant Gen as AddressGenerator
    
    Engine->>Pool: random_search()
    Pool->>Worker: 提交N个worker任务
    
    loop 每个Worker循环
        Worker->>KeyMgr: generate_key()
        Note over Worker,KeyMgr: 生成随机私钥<br/>secrets.token_bytes(32)
        KeyMgr-->>Worker: 返回私钥
        
        Worker->>Dedup: check_and_add(private_key)
        Dedup-->>Worker: 是否重复
        
        alt 未重复
            Worker->>Gen: generate_address(private_key)
            Note over Worker,Gen: 私钥→公钥→Hash160→Base58
            Gen-->>Worker: 返回地址
            
            Worker->>Worker: 检查地址是否在targets中
            
            alt 匹配成功
                Worker->>Engine: on_match(private_key, address, wif)
                Note over Worker,Engine: 传递私钥副本<br/>调用者负责安全处理
            else 未匹配
                Worker->>KeyMgr: 退出with块
                Note over Worker,KeyMgr: 私钥自动清零
            end
        else 重复
            Worker->>KeyMgr: 继续下一轮
            Note over Worker,KeyMgr: 私钥自动清零
        end
    end
    
    Pool-->>Engine: 收集所有worker结果

```python

**随机碰撞特点**:

- 使用SecureKeyManager确保私钥安全

- 去重过滤器避免重复计算

- 私钥未匹配时自动清零

- 匹配时传递私钥副本给回调函数

### 3.2 范围扫描模式

**图3.2**: 范围扫描序列图（Mermaid sequenceDiagram）

```mermaid
sequenceDiagram
    participant Engine as Engine
    participant Pool as ThreadPool
    participant Worker as Worker (Range)
    participant Stats as Stats
    
    Engine->>Pool: range_scan(start, end)
    Engine->>Engine: 计算chunk_size<br/>total_range / num_workers
    
    loop 每个Worker处理一个chunk
        Pool->>Worker: 分配范围<br/>[worker_start, worker_end]
        
        loop k from start to end
            Worker->>Worker: k.to_bytes(32, 'big')
            Worker->>Worker: generate_address(private_key)
            
            alt 匹配成功
                Worker->>Stats: add_match(private_key, address)
                Worker->>Engine: on_match()
            end
            
            opt 每500次更新
                Worker->>Engine: _live_range_count += 500
                Note over Worker,Engine: 实时计数器<br/>减少锁竞争
            end
        end
        
        Worker-->>Engine: 返回local_count
    end
    
    Engine->>Stats: update(total_count, total_range)

```python

**范围扫描特点**:

- 均匀分块，每个Worker处理连续范围

- 实时计数器_live_range_count减少锁竞争

- 支持ETA计算（总范围已知）

- 顺序扫描，适合已知私钥范围

---

## 7. 程序运行完整流程 - 新增

**图7.1**: 完整程序运行流程图（Mermaid flowchart TD）

```mermaid
flowchart TD
    Start(["程序启动<br/>Program Start"]) --> Mode{"选择运行模式<br/>Select Mode"}
    
    Mode -->|CLI| CLIInit["解析命令行参数<br/>Parse CLI Args"]
    Mode -->|GUI| GUIInit["创建Tkinter窗口<br/>Create GUI Window"]
    
    CLIInit --> LoadTargets["加载目标地址<br/>Load Target Addresses"]
    GUIInit --> LoadTargets
    
    LoadTargets --> CreateEngine["创建碰撞引擎<br/>Create Collision Engine"]
    CreateEngine --> InitComponents["初始化组件<br/>Initialize Components"]
    
    InitComponents --> CheckpointMgr["CheckpointManager<br/>断点管理器"]
    InitComponents --> DedupFilter["DeduplicationFilter<br/>去重过滤器"]
    InitComponents --> CollisionStats["CollisionStats<br/>统计管理器"]
    InitComponents --> DataLogger["DataLogger<br/>数据日志"]
    InitComponents --> MonitorSys["MonitoringSystem<br/>监控系统"]
    
    InitComponents --> SelectBackend["选择加密后端<br/>Select Crypto Backend"]
    SelectBackend --> BackendCheck{"检查可用后端<br/>Check Available Backends"}
    
    BackendCheck -->|coincurve可用| UseCoincurve["使用CoincurveBackend<br/>性能最优 3000-5000/s"]
    BackendCheck -->|OpenSSL可用| UseOpenSSL["使用OpenSSLBackend<br/>2000-3000/s"]
    BackendCheck -->|都不行| UsePurePython["使用PurePythonBackend<br/>回退方案 1000/s"]
    
    UseCoincurve --> StartEngine
    UseOpenSSL --> StartEngine
    UsePurePython --> StartEngine
    
    StartEngine["启动碰撞引擎<br/>Start Engine"] --> RunMode{"运行模式<br/>Run Mode"}
    
    RunMode -->|random| RandomSearch["random_search<br/>随机碰撞"]
    RunMode -->|range| RangeScan["range_scan<br/>范围扫描"]
    RunMode -->|brute_force| BruteForce["brute_force<br/>暴力穷举"]
    
    RandomSearch --> WorkerLoop["Worker线程循环<br/>Worker Thread Loop"]
    RangeScan --> WorkerLoop
    BruteForce --> WorkerLoop
    
    WorkerLoop --> SecureKey["SecureKeyManager<br/>生成私钥"]
    SecureKey --> GenAddress["生成地址<br/>私钥→公钥→Hash160→Base58"]
    GenAddress --> CheckMatch{"匹配目标?<br/>Match Target?"}
    
    CheckMatch -->|是| OnMatch["触发on_match回调<br/>传递私钥副本"]
    CheckMatch -->|否| ClearKey["私钥自动清零<br/>Auto Clear Key"]
    
    ClearKey --> UpdateStats["更新统计<br/>Update Statistics"]
    OnMatch --> UpdateStats
    
    UpdateStats --> LogData["记录数据日志<br/>每5秒 Log Data"]
    LogData --> MonitorData["监控系统采集<br/>每5秒 Monitor"]
    MonitorData --> CheckAnomaly{"异常检测<br/>Anomaly Check"}
    
    CheckAnomaly -->|正常| ContinueLoop["继续循环<br/>Continue"]
    CheckAnomaly -->|异常| Alert["生成告警<br/>Generate Alert"]
    Alert --> ContinueLoop
    
    ContinueLoop --> CheckStop{"停止信号?<br/>Stop Signal?"}
    CheckStop -->|否| WorkerLoop
    CheckStop -->|是| StopEngine["停止引擎<br/>Stop Engine"]
    
    StopEngine --> SaveFinalCheckpoint["保存最终断点<br/>Save Final Checkpoint"]
    SaveFinalCheckpoint --> GenerateReport["生成数据报告<br/>Generate Report"]
    GenerateReport --> End(["程序结束<br/>Program End"])
    
    style Start fill:#e1f5ff
    style Mode fill:#fff3e0
    style End fill:#e1f5ff
    style CheckMatch fill:#ffebee
    style OnMatch fill:#c8e6c9
    style ClearKey fill:#e8f5e9
    style CheckStop fill:#fff3e0

```yaml

**流程说明**:

**1. 启动阶段**：

   - CLI/GUI两种启动方式

   - 加载目标地址集合

   - 初始化所有组件（断点、去重、统计、日志、监控）

**2. 后端选择**：

   - 优先级：Coincurve > OpenSSL > ECDSA > PurePython

   - 自动检测可用后端

   - 性能差异：3-5倍

**3. 碰撞循环**：

   - SecureKeyManager生成私钥

   - 地址生成：私钥→公钥→Hash160→Base58Check

   - 匹配检查：O(1) Set查找

   - 私钥安全：未匹配自动清零，匹配传递副本

**4. 监控与日志**：

   - 每5秒记录性能数据

   - 异常检测与告警

   - 数据保存到JSON文件

**5. 停止阶段**：

   - 保存最终断点

   - 生成数据报告

   - 优雅退出

---

*注：文档持续更新中，更多流程图将陆续补充...*

---

## 4. 地址生成流程

### 4.1 完整地址生成流程

**图4.1**: P2PKH地址生成完整流程图（Mermaid flowchart TD）

```mermaid
flowchart TD
    A["私钥生成<br/>secrets.token_bytes(32)"] --> B["私钥验证<br/>1 <= k < N"]
    B --> C["椭圆曲线标量乘法<br/>Q = k * G"]
    C --> D["公钥输出<br/>压缩33字节/非压缩65字节"]
    D --> E["SHA-256哈希<br/>32字节"]
    E --> F["RIPEMD-160哈希<br/>Hash160 20字节"]
    F --> G["添加版本字节0x00<br/>+ 校验和4字节"]
    G --> H["Base58Check编码<br/>以'1'开头的地址"]
    
    style A fill:#e1f5ff
    style B fill:#fff3e0
    style C fill:#e8f5e9
    style D fill:#f3e5f5
    style E fill:#fff3e0
    style F fill:#fff3e0
    style G fill:#e8f5e9
    style H fill:#c8e6c9

```yaml

**详细步骤说明**:

1. **私钥生成/验证**：

   - 使用 `secrets.token_bytes(32)` 生成加密安全随机数

   - 验证 `1 <= int(private_key) < Secp256k1.N`

   - N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

2. **公钥生成（椭圆曲线标量乘法）**：

   - 计算 Q = k * G（G是secp256k1基点）

   - 压缩格式: 0x02/0x03 + x坐标（33字节）

   - 非压缩格式: 0x04 + x坐标 + y坐标（65字节）

3. **Hash160哈希**：

   - SHA256(public_key) → 32字节

   - RIPEMD160(sha256_result) → 20字节

4. **Base58Check编码**：

   - 版本字节: 0x00（主网P2PKH）

   - 载荷: 20字节Hash160

   - 校验和: double_sha256(版本+载荷)[:4]

   - Base58编码: 版本 + 载荷 + 校验和

### 4.2 椭圆曲线运算流程

**图4.2**: Montgomery Ladder标量乘法算法（Mermaid flowchart TD）

```mermaid
flowchart TD
    Start(["输入: k私钥, P椭圆曲线点"]) --> Init["初始化<br/>R0 = 无穷远点<br/>R1 = P"]
    Init --> LoopStart["循环: i从k.bit_length()-1到0"]
    
    LoopStart --> GetBit["获取bit<br/>bit = (k >> i) & 1"]
    GetBit --> BitCheck{"bit == 0?"}
    
    BitCheck -->|是| Bit0["R0 = R0 + R0 点倍乘<br/>R1 = R0 + R1 点加法"]
    BitCheck -->|否| Bit1["R0 = R0 + R1 点加法<br/>R1 = R1 + R1 点倍乘"]
    
    Bit0 --> NextIter["下一次迭代"]
    Bit1 --> NextIter
    
    NextIter --> LoopEnd{"i > 0?"}
    LoopEnd -->|是| LoopStart
    LoopEnd -->|否| Return["返回 R0<br/>Q = k * P"]
    
    Return --> End(["输出: Q椭圆曲线点"])
    
    style Start fill:#e1f5ff
    style Init fill:#fff3e0
    style BitCheck fill:#ffebee
    style Return fill:#c8e6c9
    style End fill:#e1f5ff

```python

**点加法与点倍乘公式**:

**点加法（P ≠ Q）**：

```
λ = (y2 - y1) / (x2 - x1) mod p
x3 = λ² - x1 - x2 mod p
y3 = λ(x1 - x3) - y1 mod p

```python

**点倍乘（P = Q）**：

```
λ = (3x1² + a) / (2y1) mod p
x3 = λ² - 2x1 mod p
y3 = λ(x1 - x3) - y1 mod p

```python

**曲线参数**：

- p = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F

- a = 0

- b = 7

**安全特性**：

- Montgomery Ladder恒定时间实现

- 使用条件选择代替if-else

- 避免侧信道攻击（时序分析）

---

## 5. GUI交互流程

### 5.1 开始对撞流程

**图5.1**: GUI开始碰撞序列图（Mermaid sequenceDiagram）

```mermaid
sequenceDiagram
    participant User as 用户
    participant GUI as GUI界面
    participant Panel as ControlPanel
    participant Engine as CollisionEngine
    participant Stats as StatsDisplay
    
    User->>GUI: 点击开始按钮
    GUI->>GUI: _on_start()
    
    GUI->>Panel: 获取目标地址
    Panel-->>GUI: 返回targets集合
    
    GUI->>Panel: 获取模式参数
    Panel-->>GUI: 返回mode/start/end
    
    GUI->>Engine: 创建碰撞引擎<br/>KeyCollisionEngine(targets)
    Note over GUI,Engine: 注册回调函数<br/>on_progress/on_match/on_complete
    
    GUI->>Engine: 启动引擎<br/>start(mode, **kwargs)
    Note over GUI,Engine: 后台线程启动
    
    GUI->>Panel: 更新按钮状态
    GUI->>Panel: 禁用输入控件
    GUI-->>User: 界面更新

```markdown

### 5.2 进度更新流程

**图5.2**: GUI进度更新序列图（Mermaid sequenceDiagram）

```mermaid
sequenceDiagram
    participant Worker as Worker Thread
    participant Engine as Engine
    participant Display as GUI Display
    participant Stats as Stats Display
    
    Worker->>Engine: 处理私钥<br/>generate + check
    Engine->>Stats: 更新统计数据
    
    Engine->>Display: on_progress(stats)
    Note over Engine,Display: 每0.5秒回调一次
    
    Display->>Display: root.after(0)<br/>调度到主线程
    Display->>Stats: update_stats()
    Stats-->>Display: 刷新显示数据
    
    Display-->>Engine: 界面更新完成

```python

**进度更新特点**:

- 使用`root.after(0)`确保线程安全

- 回调函数在主线程执行，避免Tkinter跨线程操作

- 每0.5秒更新一次，平衡性能与响应性

### 5.3 匹配发现流程

**图5.3**: 匹配发现与显示序列图（Mermaid sequenceDiagram）

```mermaid
sequenceDiagram
    participant Worker as Worker Thread
    participant Engine as Engine
    participant GUI as GUI界面
    participant LogFrame as Log Frame
    
    Worker->>Engine: 发现匹配!<br/>address in targets
    Engine->>Engine: 编码WIF格式
    
    Engine->>GUI: on_match(private_key, address, wif)
    Note over Engine,GUI: 传递私钥副本
    
    GUI->>GUI: root.after(0)<br/>调度到主线程
    GUI->>LogFrame: log_match()
    
    LogFrame->>LogFrame: 高亮显示匹配信息
    Note over LogFrame: 私钥/地址/WIF<br/>完整信息展示
    
    GUI->>GUI: 更新状态栏<br/>“发现匹配!”

```python

**匹配处理特点**:

- 传递私钥副本，原始私钥自动清零

- 高亮显示完整匹配信息

- 状态栏实时更新

---

## 6. 断点管理流程

### 6.1 保存断点流程

**图6.1**: 断点保存序列图（Mermaid sequenceDiagram）

```mermaid
sequenceDiagram
    participant Engine as Engine
    participant CPMgr as CheckpointManager
    participant Buffer as Buffer
    participant FileSystem as File System
    
    Engine->>CPMgr: _save_checkpoint(count)
    CPMgr->>CPMgr: should_auto_save()
    Note over CPMgr: 检查自动保存间隔
    
    CPMgr->>CPMgr: 清理敏感信息
    Note over CPMgr: 移除私钥数据<br/>只保留计数器和元数据
    
    CPMgr->>Buffer: 构建JSON数据
    Buffer->>FileSystem: 写入临时文件<br/>.tmp
    FileSystem-->>Buffer: 确认写入完成
    
    Buffer->>FileSystem: 原子重命名<br/>.tmp → .json
    Note over Buffer,FileSystem: os.replace()保证原子性
    
    CPMgr-->>Engine: 保存完成

```python

**断点保存特点**:

- 原子写入：先写入临时文件，再原子重命名

- 安全保护：清理敏感信息（私钥）

- 自动保存：根据间隔自动触发

- 崩溃恢复：即使程序崩溃也不会损坏断点文件

### 6.2 恢复断点流程

**图6.2**: 断点恢复序列图（Mermaid sequenceDiagram）

```mermaid
sequenceDiagram
    participant User as 用户
    participant GUI as GUI界面
    participant Engine as Engine
    participant CPMgr as CheckpointManager
    participant FileSystem as File System
    
    User->>GUI: 点击恢复断点
    GUI->>Engine: resume_from_checkpoint()
    Engine->>CPMgr: 加载断点数据
    
    CPMgr->>FileSystem: 检查文件存在<br/>exists()
    FileSystem-->>CPMgr: 文件存在
    
    CPMgr->>FileSystem: 读取JSON文件
    FileSystem-->>CPMgr: 返回JSON数据
    
    CPMgr->>CPMgr: 解析数据
    CPMgr->>CPMgr: 版本检查<br/>version == 1
    
    CPMgr-->>Engine: 恢复统计数据
    CPMgr-->>Engine: 恢复目标集合
    
    Engine->>Engine: start(resume=True)
    Engine-->>GUI: 从断点继续运行
    GUI-->>User: 显示恢复成功

```python

**断点恢复特点**:

- 版本检查：确保断点文件格式兼容

- 数据验证：检查JSON完整性和有效性

- 状态恢复：恢复计数器、目标集合、引擎状态

- 无缝继续：从上次停止的位置继续碰撞检测

---

## 7. 并发模型

### 7.1 线程结构

**图7.1**: 多线程架构图（Mermaid graph TD）

```mermaid
graph TD
    MainThread["主线程 Main Thread<br/>GUI事件循环"]
    
    subgraph Main["主线程职责"]
        M1["GUI事件循环<br/>Tkinter mainloop"]
        M2["用户交互处理"]
        M3["进度UI更新<br/>root.after"]
        M4["引擎生命周期管理"]
    end
    
    MainThread --> M1
    MainThread --> M2
    MainThread --> M3
    MainThread --> M4
    
    MainThread -->|启动| EngineThread["引擎线程 Engine Thread<br/>KeyCollisionEngine.start()"]
    
    subgraph Engine["引擎线程职责"]
        E1["调用碰撞模式<br/>random/range/brute"]
        E2["管理ThreadPoolExecutor"]
        E3["协调工作线程"]
        E4["进度回调 on_progress"]
    end
    
    EngineThread --> E1
    EngineThread --> E2
    EngineThread --> E3
    EngineThread --> E4
    
    EngineThread -->|提交任务| WorkerPool["工作线程池 Worker Threads<br/>ThreadPoolExecutor"]
    
    subgraph Workers["工作线程"]
        W0["Worker 0<br/>生成私钥+检查去重<br/>生成地址+检查匹配"]
        W1["Worker 1<br/>生成私钥+检查去重<br/>生成地址+检查匹配"]
        W2["Worker 2<br/>生成私钥+检查去重<br/>生成地址+检查匹配"]
        WN["Worker N<br/>生成私钥+检查去重<br/>生成地址+检查匹配"]
    end
    
    WorkerPool --> W0
    WorkerPool --> W1
    WorkerPool --> W2
    WorkerPool --> WN
    
    style MainThread fill:#e1f5ff
    style EngineThread fill:#fff3e0
    style WorkerPool fill:#e8f5e9

```python

**线程结构说明**:

- **主线程**：负责GUI事件循环和用户交互，不执行碰撞计算

- **引擎线程**：协调工作线程池，管理碰撞任务生命周期

- **工作线程池**：并行执行私钥生成、地址计算、匹配检查

### 7.2 同步机制

**图7.2**: 线程同步机制图（Mermaid graph LR）

```mermaid
graph LR
    subgraph Engine["KeyCollisionEngine"]
        StopEvent["_stop_event<br/>Event<br/>优雅停止信号"]
        CountLock["_count_lock<br/>Lock<br/>保护计数器"]
        MatchesLock["_matches_lock<br/>Lock<br/>保护匹配列表"]
    end
    
    subgraph Stats["CollisionStats"]
        StatsLock["_lock<br/>Lock<br/>保护统计数据"]
    end
    
    subgraph Dedup["DeduplicationFilter"]
        DedupLock["_lock<br/>Lock<br/>保护去重集合"]
    end
    
    subgraph Checkpoint["CheckpointManager"]
        FileLock["_lock<br/>Lock<br/>保护文件操作"]
    end
    
    subgraph Crypto["CryptoBackendManager"]
        InstanceLock["_instance_lock<br/>RLock<br/>保护后端状态"]
    end
    
    style StopEvent fill:#ffebee
    style CountLock fill:#fff3e0
    style MatchesLock fill:#fff3e0
    style StatsLock fill:#e8f5e9
    style DedupLock fill:#f3e5f5
    style FileLock fill:#e8f5e9
    style InstanceLock fill:#fff3e0

```python

**同步对象说明**:

| 同步对象 | 类型 | 用途 | 位置 |
|----------|------|------|------|
| `_stop_event` | Event | 优雅停止信号 | KeyCollisionEngine |
| `_count_lock` | Lock | 保护计数器 | KeyCollisionEngine |
| `_matches_lock` | Lock | 保护匹配列表 | KeyCollisionEngine |
| `_lock` | Lock | 保护统计数据 | CollisionStats |
| `_lock` | Lock | 保护去重集合 | DeduplicationFilter |
| `_lock` | Lock | 保护文件操作 | CheckpointManager |
| `_instance_lock` | RLock | 保护后端状态 | CryptoBackendManager |

**线程安全设计**:

- 使用Event实现优雅停止，避免强制终止线程

- 使用Lock保护共享数据，避免竞态条件

- 使用RLock支持递归锁定（CryptoBackendManager）

- 最小化临界区，减少锁竞争

---

## 8. GPU碰撞工作流程

### 8.1 GPU设备初始化流程

**图8.1**: GPU设备初始化序列图（Mermaid sequenceDiagram）

```mermaid
sequenceDiagram
    participant Engine as GPU Engine
    participant Device as GPUDevice
    participant Platform as OpenCL Platform
    participant DevInfo as Device Info
    
    Engine->>Device: 创建GPU引擎<br/>GPUCollisionEngine()
    Device->>Platform: 检测OpenCL设备<br/>cl.get_platforms()
    Platform-->>Device: 返回设备列表
    
    Device->>Device: 过滤CPU/核显
    Note over Device: 排除Intel CPU<br/>保留独立GPU
    
    Device->>Device: 选择最佳设备<br/>NVIDIA > AMD > Intel
    
    Device->>DevInfo: 创建设备<br/>cl.Device()
    DevInfo->>DevInfo: 验证能力<br/>compute units, memory
    DevInfo-->>Device: 设备能力确认
    
    Device->>Device: 创建Context/Queue<br/>cl.Context, cl.CommandQueue
    Device-->>Engine: 初始化完成

```python

**GPU设备选择策略**:

- 优先级：NVIDIA > AMD > Intel GPU

- 过滤掉CPU和核显

- 验证计算单元数量和显存大小

- 自动选择性能最优设备

### 8.2 GPU批量处理流程

**图8.2**: GPU批量处理序列图（Mermaid sequenceDiagram）

```mermaid
sequenceDiagram
    participant Engine as Engine
    participant GPUDevice as GPUDevice
    participant GPUKernel as GPU Kernel<br/>(OpenCL)
    participant HostCPU as Host CPU
    
    Engine->>GPUDevice: 开始随机搜索<br/>gpu_random_search()
    GPUDevice->>GPUDevice: 生成私钥批次<br/>65536个
    
    GPUDevice->>GPUKernel: 传输私钥到GPU<br/>cl.Buffer
    Note over GPUDevice,GPUKernel: PCIe传输
    
    GPUKernel->>GPUKernel: 并行计算<br/>65536工作项
    Note over GPUKernel: for each work_item:<br/>私钥→公钥→Hash160
    
    GPUKernel->>HostCPU: 返回Hash160结果<br/>cl.enqueue_read_buffer
    Note over GPUKernel,HostCPU: PCIe传输回CPU
    
    HostCPU->>HostCPU: 检查匹配<br/>CPU端O(1)查找
    
    alt 匹配成功
        HostCPU->>Engine: 触发on_match回调
    else 未匹配
        HostCPU->>Engine: 继续下一批
    end
    
    Engine->>Engine: 更新统计
    Engine->>GPUDevice: 生成下一批

```python

**GPU批量处理特点**:

- 批次大小：65536个工作项

- 并行计算：GPU端完成私钥→公钥→Hash160

- 数据传输：PCIe总线（主要瓶颈）

- 匹配检查：CPU端完成（避免GPU分支分化）

### 8.3 GPU错误恢复流程

**图8.3**: GPU错误恢复序列图（Mermaid sequenceDiagram）

```mermaid
sequenceDiagram
    participant Engine as Engine
    participant Kernel as GPU Kernel Execution
    participant ErrorHandler as Error Handler
    participant Stats as Stats
    
    Engine->>Kernel: 执行GPU计算<br/>execute_kernel()
    
    alt 发生异常
        Kernel->>ErrorHandler: 捕获OpenCL异常
        
        ErrorHandler->>ErrorHandler: 错误分类
        
        alt 资源不足
            ErrorHandler->>ErrorHandler: 记录资源错误<br/>CL_MEM_OBJECT_ALLOCATION_FAILURE
        else 运行时错误
            ErrorHandler->>ErrorHandler: 记录运行时错误<br/>CL_EXEC_STATUS_ERROR
        end
        
        ErrorHandler->>Stats: 记录错误计数
        ErrorHandler->>Engine: 返回True<br/>继续执行
    else 正常完成
        Kernel-->>Engine: 返回结果
    end
    
    Engine->>Engine: 继续下一批

```python

**错误恢复策略**:

- 资源不足：记录错误，尝试减小批次大小

- 运行时错误：记录错误，跳过当前批次

- 不中断引擎：错误处理后继续执行

- 错误统计：便于后续分析

### 8.4 GPU vs CPU工作流对比

**图8.4**: GPU与CPU工作流对比图（Mermaid flowchart LR）

```mermaid
flowchart LR
    subgraph CPU["CPU工作流"]
        C1["私钥生成<br/>CPU"] --> C2["椭圆曲线运算<br/>CPU 单线程"]
        C2 --> C3["Hash160计算<br/>CPU"]
        C3 --> C4["目标匹配<br/>CPU"]
        C4 --> C5["统计更新"]
    end
    
    subgraph GPU["GPU工作流"]
        G1["私钥批次生成<br/>CPU"] --> G2["传输到GPU显存<br/>PCIe"]
        G2 --> G3["椭圆曲线运算<br/>GPU 65536并行"]
        G3 --> G4["Hash160计算<br/>GPU 65536并行"]
        G4 --> G5["传输回CPU<br/>PCIe"]
        G5 --> G6["目标匹配<br/>CPU"]
        G6 --> G7["统计更新"]
    end
    
    style CPU fill:#e8f5e9
    style GPU fill:#fff3e0

```python

**性能对比**:

| 指标 | CPU模式 | GPU模式 | 提升倍数 |
|------|---------|---------|----------|
| 并行度 | 4-8线程 | 65536工作项 | 8000-16000x |
| 速度 | 1000-5000 keys/s | 100k-500k keys/s | 100-100x |
| 瓶颈 | CPU计算能力 | PCIe带宽 | - |
| 适用场景 | 小规模/测试 | 大规模/生产 | - |

---

## 9. 监控数据流程 - 新增

### 9.1 性能数据采集流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Engine    │     │  Collision  │     │ Data        │     │  Data       │
│   Loop      │     │   Stats     │     │ Collector   │     │  Storage    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │                   │
       │ 运行中...         │                   │                   │
       │                   │                   │                   │
       │ 更新统计          │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │                   │ 定时采集(5秒)     │                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │ 收集性能数据      │
       │                   │                   │ (CPU/内存/速度)   │
       │                   │                   │                   │
       │                   │                   │ 收集系统数据      │
       │                   │                   │ (OS/Python/PID)   │
       │                   │                   │                   │
       │                   │                   │ 收集引擎数据      │
       │                   │                   │ (模式/状态/位置)  │
       │                   │                   │                   │
       │                   │                   │ 保存数据          │
       │                   │                   │──────────────────>│
       │                   │                   │                   │
       │                   │                   │                   │ 写入JSON
       │                   │                   │                   │ 文件
       │                   │                   │                   │

```markdown

### 9.2 数据日志记录流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Engine    │     │  Data       │     │  Data       │     │  JSON       │
│             │     │  Logger     │     │  Files      │     │  Storage    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │                   │
       │ 定时记录(5秒)     │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │                   │ 记录性能数据      │                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │ current_data.json │
       │                   │                   │ (最新数据)        │
       │                   │                   │                   │
       │                   │ 添加历史数据      │                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │ history_data.json │
       │                   │                   │ (最多1000条)      │
       │                   │                   │                   │
       │                   │ 写入性能日志      │                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │ performance.log   │
       │                   │                   │ (CSV格式)         │
       │                   │                   │                   │

```markdown

### 9.3 异常检测与告警流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Data        │     │  Anomaly    │     │   Alert     │     │   Log       │
│ Collector   │     │  Detector   │     │   System    │     │   Output    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │                   │
       │ 采集数据          │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │                   │ 检查阈值          │                   │
       │                   │                   │                   │
       │                   │ 速度 < 100?       │                   │
       │                   │   │               │                   │
       │                   │   └─ 是: 异常     │                   │
       │                   │                   │                   │
       │                   │ CPU > 90%?        │                   │
       │                   │   │               │                   │
       │                   │   └─ 是: 异常     │                   │
       │                   │                   │                   │
       │                   │ 内存 > 1024MB?    │                   │
       │                   │   │               │                   │
       │                   │   └─ 是: 异常     │                   │
       │                   │                   │                   │
       │                   │ 发现异常          │                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │ 生成告警          │
       │                   │                   │──────────────────>│
       │                   │                   │                   │
       │                   │                   │                   │ [ALERT]
       │                   │                   │                   │ 告警消息
       │                   │                   │                   │

```markdown

### 9.4 报告生成流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Timer     │     │  Report     │     │  Data       │     │  Report     │
│   (整点)    │     │  Generator  │     │  Storage    │     │  File       │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │                   │
       │ 整点触发          │                   │                   │
       │ (每小时)          │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │                   │ 读取历史数据      │                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │ history_data.json │
       │                   │                   │<──────────────────│
       │                   │                   │                   │
       │                   │ 过滤今日数据      │                   │
       │                   │                   │                   │
       │                   │ 计算统计          │                   │
       │                   │ (平均/最大/最小)  │                   │
       │                   │                   │                   │
       │                   │ 分析趋势          │                   │
       │                   │                   │                   │
       │                   │ 生成建议          │                   │
       │                   │                   │                   │
       │                   │ 保存报告          │                   │
       │                   │──────────────────────────────────────>│
       │                   │                   │                   │
       │                   │                   │                   │ report_YYYY-MM-DD.json
       │                   │                   │                   │

```markdown

### 9.5 GPU监控数据流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ GPU         │     │  GPU        │     │  Data       │     │  Data       │
│ Engine      │     │  Monitor    │     │  Storage    │     │  Files      │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │                   │
       │ 运行中...         │                   │                   │
       │                   │                   │                   │
       │ 跟踪显存使用      │                   │                   │
       │──────────────────>│                   │                   │
       │                   │                   │                   │
       │                   │ 获取GPU指标       │                   │
       │                   │ (5秒缓存)         │                   │
       │                   │                   │                   │
       │                   │ 更新显存数据      │                   │
       │                   │──────────────────>│                   │
       │                   │                   │                   │
       │                   │                   │ 保存监控数据      │
       │                   │                   │                   │

```python

---

## 10. Mermaid可视化流程图 - 新增

### 10.1 GPU工作流Mermaid图

```mermaid
sequenceDiagram
    participant E as Engine
    participant GD as GPUDevice
    participant GK as GPUKernel
    participant CPU as Host CPU
    
    E->>GD: initialize()
    GD->>GD: detect_devices()
    GD->>GD: select_best_device()
    GD->>GD: create_context()
    GD-->>E: 初始化完成
    
    E->>E: generate_private_keys()
    E->>GK: transfer_to_gpu()
    GK->>GK: parallel_compute()
    GK->>GK: scalar_multiply()
    GK->>GK: hash160()
    GK->>CPU: return_results()
    CPU->>CPU: check_matches()
    CPU-->>E: update_stats()

```markdown

### 10.2 监控数据流Mermaid图

```mermaid
flowchart TD
    A[碰撞引擎] --> B[CollisionStats]
    B --> C[DataCollector]
    C --> D{数据类型}
    D -->|性能| E[Performance Data]
    D -->|系统| F[System Data]
    D -->|引擎| G[Engine Data]
    E --> H[DataStorage]
    F --> H
    G --> H
    H --> I[current_data.json]
    H --> J[history_data.json]
    H --> K[error_log.json]
    C --> L[AnomalyDetector]
    L --> M{异常?}
    M -->|是| N[AlertSystem]
    M -->|否| O[继续监控]
    N --> P[生成告警]
    H --> Q[ReportGenerator]
    Q --> R[每日报告]

```markdown

### 10.3 完整系统架构Mermaid图

```mermaid
graph TB
    subgraph 用户界面
        CLI[CLI界面]
        GUI[GUI界面]
    end
    
    subgraph 碰撞引擎
        CPU_E[CPU引擎]
        GPU_E[GPU引擎]
    end
    
    subgraph 核心模块
        Crypto[加密后端]
        Secp[secp256k1]
        OpenCL[OpenCL内核]
    end
    
    subgraph 监控系统
        Monitor[MonitoringSystem]
        GPUMon[GPUMonitor]
        DataLog[DataLogger]
    end
    
    subgraph 数据存储
        JSON[JSON文件]
        Logs[日志文件]
    end
    
    CLI --> CPU_E
    GUI --> CPU_E
    CLI --> GPU_E
    GUI --> GPU_E
    
    CPU_E --> Crypto
    Crypto --> Secp
    GPU_E --> OpenCL
    
    CPU_E --> Monitor
    GPU_E --> Monitor
    GPU_E --> GPUMon
    
    Monitor --> DataLog
    Monitor --> JSON
    DataLog --> JSON
    DataLog --> Logs
    GPUMon --> JSON

```

---

*文档更新时间: 2026-04-20*
