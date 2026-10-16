同学们好,这一讲我们聊聊 Python 的文件 I/O。

数据处理离不开文件。Python 提供了强大的文件操作 API,核心是 open 函数。

最推荐的文件操作方式是 with 语句。with open("data.txt", "r", encoding="utf-8") as f: content = f.read() 这样写,无论是否抛异常,文件都会被正确关闭。with 的本质是上下文管理器协议,通过 __enter__ 和 __exit__ 两个魔术方法实现。

文件模式有几种:r 读,w 写(覆盖),a 追加,x 排他创建。还可以加 b 表示二进制,加 + 表示同时读写。处理文本文件用文本模式,处理图片、音频、网络数据用二进制模式。Windows 默认编码是 GBK,跨平台代码必须显式指定 encoding 等于 utf-8,否则会乱码。

除了传统的 os.path,Python 还提供了更现代的 pathlib 模块。Path 对象支持链式调用,Path("a") / "b" / "c.txt" 就能拼接路径,跨平台自动处理 Windows 反斜杠和 Unix 正斜杠的差异。Path 还提供 read_text、write_text、glob、rglob 等高级方法,比 os.path 直观很多。

文件操作的两个常见反模式:一是用 read 一次读入大文件,内存可能爆;二是忘记 close,导致文件句柄泄漏。养成 with 习惯,这两个问题自动解决。

下一讲我们学习 CSV 和 JSON,这两种结构化数据格式是数据交换的事实标准。CSV 用 csv 模块,JSON 用 json 模块,都要掌握 ensure_ascii 参数和自定义对象序列化。

编码问题在 Windows 系统上特别常见。如果不显式指定 encoding,Windows 默认是 GBK,而 Linux 和 macOS 默认是 UTF-8,跨平台代码经常因此乱码。养成好习惯,所有 open 调用都加上 encoding 等于 utf-8。

二进制文件处理与文本不同,要用 rb 或 wb 模式,读写的是 bytes 而不是 str。图片、音频、视频、网络数据都属于二进制。处理大文件时,用 chunk 方式分块读取,避免一次性加载到内存。

路径操作也是日常高频需求。除了 pathlib,还有临时文件处理场景:tempfile 模块提供 NamedTemporaryFile 和 TemporaryDirectory,自动清理临时文件,适合测试和中间数据存储。

好,这一讲就到这里,大家记得动手实践。
