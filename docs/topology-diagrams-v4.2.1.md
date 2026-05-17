# BTC碰撞引擎拓扑图文档 v3.5.1

> **版本**: v3.5.1 (Phase 6) | **最后更新**: 2026-05-08
> **面向**: 开发者/架构师
> **更新说明**: 新增 GPU Phase 6 重构架构、异步双缓冲数据流、监控告警、CLI/Wizard 交互、配置管理等拓扑图

## 目录

- [图1: 系统整体架构拓扑图 (v3.5.1 更新)](#图1-系统整体架构拓扑图)
- [图2: GPU引擎 Phase 6 重构架构拓扑图 (全新)](#图2-gpu引擎-phase-6-重构架构拓扑图)
- [图3: 核心密码学模块关系图 (v3.5.1 更新)](#图3-核心密码学模块关系图)
- [图4: 碰撞检测完整数据流拓扑图 (v3.5.1 更新)](#图4-碰撞检测完整数据流拓扑图)
- [图5: GPU异步双缓冲数据流拓扑图 (全新)](#图5-gpu异步双缓冲数据流拓扑图)
- [图6: 监控与告警系统拓扑图 (全新)](#图6-监控与告警系统拓扑图)
- [图7: 模块间依赖关系拓扑图 (v3.5.1 更新)](#图7-模块间依赖关系拓扑图)
- [图8: CLI/Wizard 交互拓扑图 (全新)](#图8-cliwizard-交互拓扑图)
- [图9: 配置管理系统拓扑图 (全新)](#图9-配置管理系统拓扑图)
- [图10: 技术栈与外部依赖拓扑图 (v3.5.1 更新)](#图10-技术栈与外部依赖拓扑图)
- [图11: 测试体系拓扑图 (全新)](#图11-测试体系拓扑图)

---

## 图1: 系统整体架构拓扑图

BTC碰撞引擎 v3.5.1 的 10 层架构拓扑图，展示从用户界面到底层 GPU 驱动的完整层级关系。

```mermaid
graph TB
    subgraph UserInterface["用户界面层"]
        CLI["命令行界面<br/>src/cli/ 19文件"]
        Wizard["交互式向导<br/>src/wizard/ 11文件"]
        GUI["图形界面<br/>key_collision_gui.py"]
    end

    subgraph EngineLayer["碰撞引擎层"]
        CPUEngine["CPU碰撞引擎<br/>KeyCollisionEngine"]
        GPUEngineShim["GPU引擎 Shim层<br/>gpu_collision_engine.py<br/>78行 向后兼容"]
        MPEngine["多进程引擎<br/>MultiprocessEngine"]
        HybridEngine["混合引擎<br/>HybridEngine"]
    end

    subgraph GPUPhase6["GPU引擎 Phase 6 子模块"]
        GPUCoord["引擎协调器<br/>engine.py 1109行"]
        Facade["外观层<br/>facade.py"]
        Core["碰撞核心<br/>core.py"]
        Monitoring["监控管道<br/>monitoring.py"]
        Vendor["厂商策略<br/>vendor_strategy.py"]
        Protocols["协议定义<br/>protocols.py 5接口"]
    end

    subgraph CryptoBackend["加密后端层"]
        CryptoMgr["加密后端管理器<br/>CryptoBackendManager"]
        PurePython["PurePython后端"]
        OpenSSL["OpenSSL后端"]
        Coincurve["Coincurve后端 libsecp256k1"]
        ECDSA["ECDSA后端"]
    end

    subgraph CoreCrypto["核心密码学层"]
        Secp256k1["secp256k1 椭圆曲线"]
        AddrGen["地址生成器"]
        Precompute["预计算点表"]
        BigInt["大整数优化 gmpy2"]
        SIMD["SIMD哈希优化"]
        MemPool["内存池"]
        SecureKey["安全密钥管理"]
        KeyGen["密钥生成器"]
    end

    subgraph MonitorLayer["监控与告警层"]
        MonSys["增强型监控系统"]
        DataLogger["数据日志"]
        GPUPerfMon["GPU性能监控"]
        AlertSys["告警系统"]
        NotifCh["多渠道通知"]
    end

    subgraph DataLayer["数据存储层"]
        Checkpoint["断点管理器"]
        Dedup["去重过滤器 Bloom"]
        Stats["碰撞统计"]
        MatchStorage["匹配存储"]
        JSONFiles["JSON数据文件"]
        LogFiles["日志文件"]
    end

    subgraph GPULayer["GPU加速层 src/gpu/ 48文件"]
        PyOpenCL["PyOpenCL"]
        OpenCLRuntime["OpenCL运行时"]
        GPUKernel["GPU内核 kernel.py"]
        GPUDevice["GPU设备管理"]
        AsyncExec["异步执行器"]
        MemManager["GPU内存管理"]
        MultiGPU["多GPU协调"]
        LoadBal["负载均衡"]
    end

    subgraph ConfigLayer["配置层"]
        ConfigMgr["配置管理器 850行"]
        ConfigWatch["配置热重载监视器"]
        CryptoConfig["加密配置"]
        GPUConfig["GPU配置"]
        PerfConfig["性能监控配置"]
    end

    subgraph I18nLayer["国际化层"]
        Translator["翻译器 Translator"]
        LangDetect["语言检测器"]
        Locales["locales/ JSON语言文件"]
    end

    CLI --> CPUEngine
    Wizard --> CPUEngine
    Wizard --> GPUEngineShim
    GUI --> CPUEngine
    CLI --> GPUEngineShim

    GPUEngineShim --> GPUCoord
    GPUCoord --> Facade
    GPUCoord --> Core
    GPUCoord --> Monitoring
    GPUCoord --> Vendor
    Facade --> Protocols

    CPUEngine --> CryptoMgr
    GPUCoord --> CryptoMgr
    GPUCoord --> GPUDevice
    GPUDevice --> PyOpenCL
    PyOpenCL --> OpenCLRuntime

    CryptoMgr --> Coincurve
    CryptoMgr --> OpenSSL
    CryptoMgr --> ECDSA
    CryptoMgr --> PurePython
    PurePython --> Secp256k1
    PurePython --> AddrGen
    AddrGen --> Precompute
    AddrGen --> BigInt
    AddrGen --> SIMD
    AddrGen --> MemPool

    CPUEngine --> MonSys
    GPUCoord --> MonSys
    MonSys --> DataLogger
    MonSys --> GPUPerfMon
    MonSys --> AlertSys
    AlertSys --> NotifCh

    CPUEngine --> Checkpoint
    CPUEngine --> Dedup
    CPUEngine --> Stats
    GPUCoord --> Stats
    Checkpoint --> JSONFiles
    DataLogger --> JSONFiles
    MonSys --> LogFiles

    CPUEngine --> ConfigMgr
    GPUCoord --> ConfigMgr
    ConfigMgr --> ConfigWatch
    ConfigMgr --> CryptoConfig
    ConfigMgr --> GPUConfig
    ConfigMgr --> PerfConfig

    CLI --> Translator
    Wizard --> Translator
    Translator --> LangDetect
    Translator --> Locales
```

---

## 图2: GPU引擎 Phase 6 重构架构拓扑图

展示 GPU 引擎从原始 1,466 行单体到 Phase 6 重构后的分布式架构。

```mermaid
graph TB
    subgraph Phase6["Phase 6 引擎协调器 engine.py 1109行"]
        Engine["GPUCollisionEngine<br/>组合所有Phase 2-5组件"]
    end

    subgraph Phase1["Phase 1: 协议定义 protocols.py"]
        Proto1["IGPUDeviceManager"]
        Proto2["IKernelExecutor"]
        Proto3["IAsyncExecutionPipeline"]
        Proto4["IMonitoringPipeline"]
        Proto5["ICollisionCore"]
        Proto6["VendorOptimizationStrategy"]
        DataTypes["GPUDevice/GPUContext<br/>MatchResult/CollisionResult<br/>GPUExecutionContext"]
    end

    subgraph Phase2["Phase 2: 外观层 facade.py"]
        Facade["GPUEngineFacade"]
        DevAdapt["DeviceManagerAdapter<br/>→ IGPUDeviceManager"]
        KernAdapt["GPUKernelAdapter<br/>→ IKernelExecutor"]
        AsyncAdapt["AsyncPipelineAdapter<br/>→ IAsyncExecutionPipeline"]
    end

    subgraph Phase3["Phase 3: 监控管道 monitoring.py"]
        PerfPipeline["PerformanceMonitoringPipeline<br/>→ IMonitoringPipeline"]
        PerfMon["性能监控"]
        AnomalyDetect["异常检测"]
        DataLog["数据日志集成"]
    end

    subgraph Phase4["Phase 4: 碰撞核心 core.py"]
        CollCore["CollisionCore<br/>→ ICollisionCore"]
        CollStats["碰撞统计 CollisionStats"]
        Checkpoint["断点管理 CheckpointManager"]
        Dedup["去重过滤 DeduplicationFilter"]
        SearchCoord["搜索模式协调器"]
    end

    subgraph Phase5["Phase 5: 厂商策略 vendor_strategy.py"]
        VendorFactory["VendorOptimizationFactory"]
        NvidiaStrat["NVIDIA优化策略"]
        AMDStrat["AMD优化策略"]
        IntelStrat["Intel优化策略"]
    end

    subgraph Shim["Shim 向后兼容层"]
        OldImport["gpu_collision_engine.py<br/>78行 重导出"]
        OldAPI["保留所有旧导入路径<br/>Monkey-patch兼容"]
    end

    subgraph GPUSubsystem["src/gpu/ 底层GPU子系统 48文件"]
        GPUDevice["GPUDevice GPUDeviceDetector"]
        GPUContext["GPUContext"]
        GPUKernel["GPUKernel kernel_impl.py"]
        AsyncExec["AsyncGPUExecutor"]
        MemPool["GPU内存池"]
        SearchModes["搜索模式 Random/Range/BruteForce"]
        MultiGPU["多GPU引擎"]
    end

    Engine --> Facade
    Engine --> PerfPipeline
    Engine --> CollCore
    Engine --> VendorFactory

    Facade --> DevAdapt
    Facade --> KernAdapt
    Facade --> AsyncAdapt

    DevAdapt --> Proto1
    KernAdapt --> Proto2
    AsyncAdapt --> Proto3
    PerfPipeline --> Proto4
    CollCore --> Proto5
    VendorFactory --> Proto6

    DevAdapt --> GPUDevice
    DevAdapt --> GPUContext
    KernAdapt --> GPUKernel
    AsyncAdapt --> AsyncExec

    CollCore --> CollStats
    CollCore --> Checkpoint
    CollCore --> Dedup
    CollCore --> SearchCoord

    VendorFactory --> NvidiaStrat
    VendorFactory --> AMDStrat
    VendorFactory --> IntelStrat

    OldImport --> Engine
    OldAPI --> OldImport
```

---

## 图3: 核心密码学模块关系图

展示核心密码学模块之间的依赖关系，包含 v3.5.0 新增的性能优化模块。

```mermaid
graph TD
    A["P2PKHAddressGenerator<br/>地址生成器"] --> B["Secp256k1<br/>椭圆曲线参数"]
    A --> C["EllipticCurve<br/>椭圆曲线运算"]
    A --> D["HashUtils<br/>SHA256/RIPEMD160"]
    B --> E["ECPoint<br/>曲线点类"]
    C --> E
    D --> F["Base58<br/>Base58Check编码"]
    F --> G["WIF<br/>私钥格式"]
    A --> H["CryptoBackendManager<br/>加密后端管理 策略模式"]
    H --> I["PurePythonBackend"]
    H --> J["OpenSSLBackend<br/>cryptography库"]
    H --> K["CoincurveBackend<br/>libsecp256k1 推荐"]
    H --> L["ECDSABackend<br/>ecdsa库"]

    subgraph OptModules["性能优化模块 v2.2+"]
        Pre["PrecomputedTable<br/>预计算点表 +46%"] --> B
        Big["BigIntOptimizer<br/>gmpy2模逆元 +1455%"] --> C
        Simd["SIMDHash<br/>AES-NI加速"] --> D
        OptAddr["OptimizedAddressGenerator<br/>组合优化"] --> A
        Mem["MemoryPool<br/>对象复用 -60%延迟"] --> A
    end

    Secure["SecureKeyManager<br/>安全密钥管理"] --> H
    KeyG["KeyGenerator<br/>密钥生成器"] --> Secure
    BitVal["BitcoinKeyValidator<br/>密钥验证器"] --> F
    BitVal --> G
    CompVal["ComplianceValidator<br/>合规性验证"] --> BitVal
```

---

## 图4: 碰撞检测完整数据流拓扑图

展示从输入到碰撞匹配的完整数据流（已验证）。

```mermaid
flowchart TD
    subgraph TargetImport["目标地址导入阶段"]
        A1["7种格式输入<br/>WIF/P2PKH/P2SH/Bech32<br/>公钥/Hash160"] --> A2["TargetResolver<br/>detect_format()"]
        A2 --> A3["resolve() 统一转换<br/>→ P2PKH地址字符串"]
        A3 --> A4["引擎初始化<br/>self.targets = Set[str]"]
        A4 --> A5["小写化存储<br/>addr.lower() O(1)查找"]
    end

    subgraph CollisionEngine["碰撞引擎运行阶段"]
        B1["私钥生成<br/>SecureKeyManager"] --> B2["地址生成<br/>P2PKHAddressGenerator"]
        B2 --> B3["椭圆曲线乘法<br/>Q = k × G → 公钥33B"]
        B3 --> B4["Hash160计算<br/>SHA256 + RIPEMD160"]
        B4 --> B5["Base58Check编码<br/>→ P2PKH地址字符串"]
    end

    subgraph MatchProcess["碰撞匹配阶段"]
        B5 --> C1["生成地址小写化<br/>addr.lower()"]
        A5 --> C2{"字符串集合查找<br/>addr.lower() in targets?<br/>O(1)查找"}
        C1 --> C2
        C2 -->|"匹配 True"| D1["触发回调<br/>on_match(pk, addr, wif)"]
        C2 -->|"不匹配 False"| D2["计数器+1<br/>继续下一个私钥"]
        D1 --> D3["更新统计<br/>CollisionStats"]
        D2 --> D3
    end

    subgraph SystemOps["系统操作"]
        B1 --> E1["断点保存<br/>CheckpointManager"]
        B1 --> E2["去重过滤<br/>DeduplicationFilter"]
        D3 --> E3["性能监控<br/>DataLogger"]
        D3 --> E4["告警检查<br/>AlertSystem"]
    end

    subgraph GPUPath["GPU加速路径"]
        B1 -.GPU模式.-> F1["批量私钥→GPU显存<br/>PRNG种子预生成"]
        F1 --> F2["GPU内核计算<br/>secp256k1 + SHA256 + RIPEMD160"]
        F2 --> F3["Hash160结果→CPU回传"]
        F3 --> C2
    end
```

---

## 图5: GPU异步双缓冲数据流拓扑图

对比展示同步模式与异步双缓冲模式的数据流差异。

```mermaid
flowchart LR
    subgraph Sync["同步模式 v3.2.0 ~2.99M keys/s"]
        S1["CPU生成私钥"] --> S2["GPU计算"]
        S2 --> S3["CPU检查结果"]
        S3 --> S1
    end

    subgraph Async["异步双缓冲模式 v3.5.1 ~4.89M keys/s +63.9%"]
        direction TB
        subgraph Phase1["阶段1"]
            A1["缓冲A: GPU计算中"]
            B1["缓冲B: CPU生成私钥"]
        end
        subgraph Phase2["阶段2"]
            A2["缓冲A: CPU检查结果"]
            B2["缓冲B: GPU计算中"]
        end
        Phase1 --> Phase2
        Phase2 --> Phase1
    end

    subgraph Pipeline["异步管道详细流程"]
        direction TB
        P1["PRNG种子预生成线程<br/>os.urandom(32)"] --> P2["种子池队列<br/>prefetch_size=4"]
        P2 --> P3["AsyncGPUExecutor<br/>run_batch_async()"]
        P3 --> P4["GPU内核执行<br/>OpenCL命令队列"]
        P4 --> P5["结果回传<br/>PCIe DMA"]
        P5 --> P6["匹配检查<br/>addr.lower() in targets"]
        P1 --> P2
    end
```

---

## 图6: 监控与告警系统拓扑图

展示 v3.5.0 增强后的监控告警系统架构。

```mermaid
graph TB
    subgraph EngineEvents["引擎事件源"]
        CPU["CPU碰撞引擎"]
        GPU["GPU碰撞引擎"]
        Multi["多进程引擎"]
    end

    subgraph Monitoring["增强型监控系统 EnhancedMonitoringSystem"]
        Collector["数据采集器"]
        DataLogger["数据日志 DataLogger<br/>→ current_data.json<br/>→ history_data.json"]
        GPUPerf["GPU性能监控器<br/>GPUPerformanceMonitor"]
    end

    subgraph AlertEngine["告警引擎 AlertSystem"]
        RuleEngine["规则引擎 5条默认规则"]
        Rule1["性能退化 >20%"]
        Rule2["内存使用 >80%"]
        Rule3["GPU温度 >85°C"]
        Rule4["错误率 >5%"]
        Rule5["吞吐量下降 >50%"]
        RateLimit["全局速率限制<br/>10条/分钟"]
        Dedup["告警去重<br/>回溯10条"]
        CoolDown["冷却时间<br/>2-10分钟/规则"]
    end

    subgraph Notifications["通知渠道"]
        Console["控制台通知"]
        LogFile["文件通知"]
        Webhook["Webhook 可选"]
        Callbacks["告警回调函数"]
    end

    subgraph Storage["告警存储"]
        AlertHistory["告警历史<br/>alert_history.json<br/>最近1000条"]
        AlertStats["告警统计<br/>按级别/类型"]
        ActiveAlerts["活跃告警列表"]
    end

    CPU --> Collector
    GPU --> Collector
    Multi --> Collector
    Collector --> DataLogger
    Collector --> GPUPerf
    DataLogger --> RuleEngine

    RuleEngine --> Rule1
    RuleEngine --> Rule2
    RuleEngine --> Rule3
    RuleEngine --> Rule4
    RuleEngine --> Rule5
    RuleEngine --> RateLimit
    RuleEngine --> Dedup
    RuleEngine --> CoolDown

    RuleEngine --> Console
    RuleEngine --> LogFile
    RuleEngine --> Webhook
    RuleEngine --> Callbacks

    RuleEngine --> AlertHistory
    AlertHistory --> AlertStats
    AlertHistory --> ActiveAlerts
```

---

## 图7: 模块间依赖关系拓扑图

展示 v3.5.1 全部 11 个 src 子模块之间的 import 依赖关系。

```mermaid
graph LR
    subgraph Core["src/core/ 密码学核心"]
        secp256k1["secp256k1.py"]
        addr_gen["address_generator.py"]
        crypto["crypto_backend.py"]
        secure_key["secure_key_manager.py"]
        mempool["memory_pool.py"]
        bigint["bigint_optimizer.py"]
    end

    subgraph Collision["src/collision/ 碰撞引擎"]
        key_engine["key_collision_engine.py"]
        gpu_shim["gpu_collision_engine.py Shim"]
        gpu_engine["gpu/engine.py Phase6"]
        chkpt["checkpoint_manager.py"]
        dedup["deduplication_filter.py"]
        stats["collision_stats.py"]
        resolver["targets/resolver.py"]
    end

    subgraph GPUSrc["src/gpu/ GPU子系统"]
        gpu_device["device.py"]
        gpu_kernel["kernel.py kernel_impl.py"]
        gpu_async["async_executor.py"]
        gpu_mem["memory_pool.py"]
        gpu_vendor["vendors/ 厂商适配"]
    end

    subgraph MonitoringMod["src/monitoring/ 监控"]
        mon_sys["monitoring_system.py"]
        alert["alert_system.py"]
        data_log["data_logger.py"]
        gpu_mon["gpu_performance_monitor.py"]
    end

    subgraph CLI["src/cli/ 命令行"]
        cli_main["main.py"]
        commands["commands.py"]
        engine_runner["engine_runner.py"]
    end

    subgraph Wizard["src/wizard/ 向导"]
        wizard_engine["wizard_engine.py"]
        selectors["selectors/ 4步选择器"]
    end

    subgraph Config["src/config/ 配置"]
        config_mgr["config_manager.py"]
        config_watch["config_watcher.py"]
    end

    subgraph Others["其他模块"]
        i18n["src/i18n/ 国际化"]
        logging["src/logging/ 日志"]
        utils["src/utils/ 工具"]
    end

    key_engine --> addr_gen
    key_engine --> secure_key
    key_engine --> chkpt
    key_engine --> dedup
    key_engine --> stats
    key_engine --> resolver
    key_engine --> mon_sys

    gpu_shim --> gpu_engine
    gpu_engine --> gpu_device
    gpu_engine --> gpu_kernel
    gpu_engine --> gpu_async
    gpu_engine --> gpu_mem
    gpu_engine --> gpu_vendor
    gpu_engine --> crypto

    gpu_engine --> mon_sys
    gpu_engine --> alert
    gpu_engine --> data_log
    gpu_engine --> gpu_mon

    cli_main --> commands
    commands --> engine_runner
    engine_runner --> key_engine
    engine_runner --> gpu_shim
    engine_runner --> config_mgr
    cli_main --> i18n

    wizard_engine --> selectors
    wizard_engine --> config_mgr
    wizard_engine --> cli_main
    wizard_engine --> i18n

    config_mgr --> config_watch
    config_mgr --> utils
    key_engine --> config_mgr
    gpu_engine --> config_mgr

    mon_sys --> data_log
    mon_sys --> alert
    alert --> gpu_mon
```

---

## 图8: CLI/Wizard 交互拓扑图

展示 CLI 命令行系统与 Wizard 交互式向导的完整交互流程。

```mermaid
graph TB
    subgraph EntryPoints["入口点"]
        MainCLI["btc-collision CLI<br/>main.py"]
        DirectWizard["wizard_engine.py<br/>独立运行"]
        StartBat["start.bat<br/>Windows启动脚本"]
    end

    subgraph CLIArch["CLI 系统架构"]
        ArgParser["arg_parser.py<br/>参数解析与验证"]
        Commands["commands.py<br/>命令分发 1200+行"]
        ConfigLoad["config_loader.py<br/>配置加载"]
        ConfigMig["config_migration.py<br/>配置版本迁移"]
        EngineBuild["engine_builder.py<br/>引擎构建器"]
        EngineRun["engine_runner.py<br/>引擎生命周期管理"]
        Output["output.py<br/>富文本输出 Rich"]
        Progress["progress.py<br/>进度显示"]
        Pagination["pagination.py<br/>分页显示"]
        LogWindow["log_window.py<br/>日志窗口"]
        KPListener["keyboard_listener.py<br/>键盘监听 Ctrl+C"]
        Validation["validation.py<br/>输入验证"]
    end

    subgraph WizardArch["Wizard 向导架构"]
        WizEngine["WizardEngine<br/>wizard_engine.py"]
        Step1["Step1: TargetSelector<br/>目标地址选择"]
        Step2["Step2: ModeSelector<br/>碰撞模式选择"]
        Step3["Step3: OptionSelector<br/>功能选项选择"]
        Step4["Step4: GPUSelector<br/>GPU加速选择"]
        Step5["Step5: ConfigBuilder<br/>配置构建"]
        Events["事件系统<br/>EventDispatcher"]
        MsgQueue["消息队列<br/>WizardMessageQueue"]
    end

    subgraph EngineAPI["引擎API"]
        createEngine["create_collision_engine()<br/>工厂函数"]
        CPUEngine["KeyCollisionEngine"]
        GPUEngine["GPUCollisionEngine<br/>Phase 6"]
    end

    MainCLI --> ArgParser
    MainCLI --> Commands
    ArgParser --> Commands
    Commands --> ConfigLoad
    Commands --> ConfigMig
    Commands --> EngineBuild
    EngineBuild --> EngineRun
    EngineRun --> Output
    EngineRun --> Progress
    EngineRun --> Pagination
    EngineRun --> KPListener

    StartBat --> MainCLI
    StartBat --> DirectWizard

    DirectWizard --> WizEngine
    WizEngine --> Step1
    WizEngine --> Step2
    WizEngine --> Step3
    WizEngine --> Step4
    WizEngine --> Step5
    WizEngine --> Events
    WizEngine --> MsgQueue
    Step5 --> Commands

    EngineBuild --> createEngine
    createEngine --> CPUEngine
    createEngine --> GPUEngine
```

---

## 图9: 配置管理系统拓扑图

展示配置管理的完整架构，包括热重载、验证和协调机制。

```mermaid
graph TB
    subgraph ConfigFiles["配置文件"]
        Defaults["DEFAULT_CONFIG<br/>5大配置区块"]
        ConfigJSON["config.json<br/>用户配置文件"]
        ConfigExample["config.example.json<br/>配置模板"]
        Schema["CONFIG_SCHEMA<br/>JSON Schema Draft7"]
    end

    subgraph ConfigCore["ConfigManager 850行"]
        Load["load_config()<br/>加载 + 注释过滤 + 验证"]
        Get["get(key)<br/>线程安全读取"]
        Set["set(key, value)<br/>线程安全写入"]
        Save["save_config()<br/>持久化保存"]
        Validate["validate()<br/>Schema + 手动双模式"]
        Merge["_merge_config()<br/>递归合并"]
        DeepCopy["_deep_copy_config()<br/>深拷贝保护"]
    end

    subgraph HotReload["热重载系统 P2-4"]
        Watcher["ConfigWatcher<br/>config_watcher.py"]
        Watchdog["watchdog后端<br/>事件驱动 响应快"]
        Polling["polling后端<br/>定期检查mtime"]
        Reload["reload_config()<br/>验证→备份→合并→回滚"]
        Callbacks["on_config_changed()<br/>变更回调通知"]
    end

    subgraph SubConfigs["子配置系统"]
        CryptoConf["CryptoConfig<br/>加密后端配置"]
        PerfConf["PerformanceConfig<br/>性能监控配置"]
        OptConf["OptimizationConfig<br/>优化策略配置"]
        Coordinator["ConfigCoordinator<br/>配置协调器"]
    end

    subgraph Consumers["配置消费者"]
        CPUEngine["CPU碰撞引擎"]
        GPUEngine["GPU碰撞引擎"]
        MonSys["监控系统"]
        AlertSys["告警系统"]
        CLI["CLI系统"]
        Wizard["向导系统"]
        I18n["i18n翻译器"]
    end

    ConfigJSON --> Load
    ConfigExample --> Load
    Defaults --> Merge
    Schema --> Validate

    Load --> Validate
    Load --> Merge
    Merge --> Get
    Merge --> Set
    Set --> Save

    ConfigJSON --> Watcher
    Watcher --> Watchdog
    Watcher --> Polling
    Watchdog --> Reload
    Polling --> Reload
    Reload --> Callbacks

    Get --> CPUEngine
    Get --> GPUEngine
    Get --> MonSys
    Get --> AlertSys
    Get --> CLI
    Get --> Wizard
    Get --> I18n

    Callbacks --> CPUEngine
    Callbacks --> GPUEngine
    Callbacks --> MonSys

    Coordinator --> CryptoConf
    Coordinator --> PerfConf
    Coordinator --> OptConf
    CryptoConf --> ConfigCore
    PerfConf --> ConfigCore
    OptConf --> ConfigCore
```

---

## 图10: 技术栈与外部依赖拓扑图

展示项目完整技术栈和依赖层次。

```mermaid
graph TD
    subgraph PythonRuntime["Python 运行时"]
        Py39["Python 3.9+ 标准库"]
        Secrets["secrets CSPRNG"]
        Hashlib["hashlib SHA256/RIPEMD160"]
        Threading["threading 多线程"]
        ConcurrentF["concurrent.futures"]
        JSON["json/ujson"]
        Logging["logging"]
        Asyncio["asyncio"]
    end

    subgraph CoreDeps["核心依赖 13个"]
        Coincurve["coincurve >=18.0<br/>libsecp256k1绑定"]
        Gmpy2["gmpy2 >=2.1<br/>大整数运算"]
        Pycrypto["pycryptodome >=3.19<br/>SIMD哈希 AES-NI"]
        Cryptography["cryptography >=43.0<br/>OpenSSL后端"]
        Cachetools["cachetools >=5.3<br/>LRU缓存"]
        Bech32["bech32 >=1.2<br/>SegWit地址"]
        ECDSA["ecdsa >=0.18<br/>ECDSA后端"]
        Psutil["psutil >=5.9<br/>系统监控"]
        PyNaCl["PyNaCl >=1.5<br/>安全内存清零"]
        Rich["rich >=13.0<br/>CLI富文本"]
        CFFI["cffi >=1.15<br/>C FFI"]
        JSONSchema["jsonschema >=4.0<br/>配置验证"]
        Setproctitle["setproctitle >=1.3<br/>进程名"]
    end

    subgraph GPUDeps["GPU可选依赖"]
        PyOpenCL["pyopencl >=2022.1<br/>OpenCL绑定"]
        Numpy["numpy >=1.24<br/>GPU数据处理"]
    end

    subgraph DevDeps["开发依赖"]
        Pytest["pytest >=9.0"]
        PytestCov["pytest-cov"]
        Mypy["mypy >=1.0"]
        Black["black >=24.0"]
        Flake8["flake8 >=6.0"]
        Bandit["bandit >=1.7"]
        Sphinx["sphinx >=7.0"]
    end

    subgraph SystemDeps["系统依赖"]
        OpenCLRT["OpenCL运行时<br/>Intel/NVIDIA/AMD"]
        GPUDriver["GPU驱动<br/>CUDA/ROCm/Arc"]
        PCIe["PCIe总线<br/>CPU-GPU传输"]
    end

    subgraph ProjectModules["项目模块"]
        Core["src/core/ 密码学"]
        Collision["src/collision/ 碰撞"]
        GPUSrc["src/gpu/ GPU子系统"]
        CLI["src/cli/ 命令行"]
        Monitoring["src/monitoring/ 监控"]
        Config["src/config/ 配置"]
        Wizard["src/wizard/ 向导"]
        I18n["src/i18n/ 国际化"]
        Utils["src/utils/ 工具"]
    end

    Core --> Coincurve
    Core --> Gmpy2
    Core --> Pycrypto
    Core --> Cryptography
    Core --> ECDSA
    Core --> Bech32
    Core --> PyNaCl
    Core --> CFFI

    Collision --> Core
    Collision --> Cachetools
    GPUSrc --> PyOpenCL
    GPUSrc --> Numpy
    GPUSrc --> OpenCLRT
    OpenCLRT --> GPUDriver
    PyOpenCL --> OpenCLRT

    CLI --> Rich
    CLI --> Setproctitle
    Monitoring --> Psutil
    Config --> JSONSchema
    Wizard --> Rich

    Core --> Py39
    Collision --> Py39
    CLI --> Py39
    Monitoring --> Py39
```

---

## 图11: 测试体系拓扑图

展示完整的测试体系架构，含 CI/CD 流水线。

```mermaid
graph TB
    subgraph TestCategories["测试分类"]
        Unit["单元测试<br/>unit marker"]
        Integration["集成测试<br/>integration marker"]
        Smoke["冒烟测试<br/>smoke marker"]
        Regression["回归测试<br/>regression marker"]
        GPUUnit["GPU单元测试<br/>gpu_unit marker"]
        GPUHW["GPU硬件测试<br/>gpu_hardware marker"]
        GPUKernel["GPU内核测试<br/>gpu_kernel marker"]
        Security["安全测试<br/>security marker"]
        PerfBench["性能基准<br/>performance/benchmark"]
        ThreadSafety["线程安全测试<br/>thread_safety marker"]
        CrossPlat["跨平台测试<br/>cross_platform marker"]
        EdgeCase["边界条件测试<br/>edge_cases marker"]
    end

    subgraph TestInfra["测试基础设施"]
        Conftest["conftest.py<br/>24KB 共享夹具"]
        MockFactory["gpu_mock_factory.py<br/>GPU Mock工厂"]
        MockPatch["gpu_mock_patch.py<br/>Mock补丁"]
        TestHelpers["test_helpers.py<br/>测试辅助函数"]
    end

    subgraph PriorityMarkers["优先级标记"]
        P1["p1_high<br/>高优先级修复"]
        P2["p2_medium<br/>中优先级修复"]
        P3["p3_low<br/>低优先级修复"]
        Flaky["flaky<br/>不稳定测试 允许重试"]
    end

    subgraph CI["CI/CD 流水线 .github/workflows/"]
        CITest["ci.yml<br/>代码质量检查"]
        Deploy["deploy.yml<br/>部署流水线"]
        DocQuality["doc-quality.yml<br/>文档质量检查"]
        Release["release.yml<br/>发布流水线"]
    end

    subgraph ToolChain["工具链"]
        Pytest["pytest + pytest-cov"]
        Coverage["覆盖率报告<br/>--cov=src"]
        Mypy["mypy 类型检查<br/>Python 3.11"]
        Black["black 格式化<br/>100字符列"]
        Flake8["flake8 代码质量<br/>E203,W503忽略"]
        Bandit["bandit 安全扫描<br/>B101跳过"]
    end

    subgraph TestResults["测试输出"]
        HTMLCover["htmlcov/<br/>HTML覆盖率"]
        XMLCover["coverage.xml<br/>CI集成"]
        TestReport["test_results/<br/>测试报告"]
        BenchResults[".benchmarks/<br/>基准数据"]
    end

    Unit --> Conftest
    Integration --> Conftest
    GPUUnit --> MockFactory
    GPUUnit --> MockPatch
    GPUHW --> Conftest
    PerfBench --> BenchResults

    CITest --> Pytest
    CITest --> Mypy
    CITest --> Black
    CITest --> Flake8
    CITest --> Bandit
    Deploy --> TestReport

    Pytest --> HTMLCover
    Pytest --> XMLCover
    Pytest --> Coverage
```
