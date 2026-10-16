同学们好,欢迎来到 Python 课程的第 18 讲,也是我们的结业课——项目实战。

今天我们要一起完成一个完整的 Python 项目:学生成绩管理系统,叫 gradebook。这个项目会用上我们学过的所有知识:数据结构、面向对象、文件 I/O、异常处理、日志、命令行解析,还有测试。

先看项目结构。src 目录放源码,分四层:models 是数据类,用 @dataclass 装饰器简化定义;storage 是持久化,负责 JSON 读写;service 是业务逻辑,组合数据模型与存储;cli 是命令行入口,用 argparse 解析参数。tests 目录放单元测试,用 pytest 框架。这种分层让业务逻辑与 I/O 分离,代码易测试、易维护。

数据模型用 dataclass 装饰器,自动生成构造和比较方法,代码量减少一半。存储层用 JSON 文件,读取时反序列化为 Student 对象,保存时序列化回去。涉及 datetime 等复杂类型时,需要自定义 default 函数。

服务层负责所有业务逻辑:添加学生、删除学生、录入成绩、计算平均分、Top-N 排行。每个方法都加异常处理,输入校验抛 ValidationError,资源缺失抛 NotFoundError,权限不足抛 PermissionDeniedError,统一继承自 AppError 基类。每个方法用 logging 模块记录关键操作。

CLI 层用 argparse 实现命令行参数解析,支持子命令 add、score、list、top、delete。子命令让工具职责清晰,add 对应添加学生,score 对应录入成绩,top 对应前 N 名。

测试用 pytest 框架,每个核心方法写 3 个以上测试用例,用 pytest fixture 提供测试数据。覆盖率要求 ≥ 80%。

项目完成后,我们可以用 pip install -e . 安装,生成可执行命令 gradebook。这个项目麻雀虽小,五脏俱全,体现了 Python 项目的工程化组织。

完整的工程化项目还包括:用 black 自动格式化代码、用 ruff 做静态检查、用 mypy 做类型检查、用 pytest 跑测试并生成覆盖率报告。这些工具应该成为你日常开发的标配。

最后,我想说:学完这门课不是终点,而是起点。Python 的世界很大,后续你可以学 Web 开发、数据科学、机器学习,任何方向都欢迎你探索。祝大家学有所成,我们下一门课再见!
