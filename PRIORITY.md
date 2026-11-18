# 固定仿射复测优先级

这是 V1 的新增业务契约；当前源码尚未实现本能力。README.md 中的正常归档、原接口、全部原测试、日样例和运行清单继续有效。本文件和 priority_cases.py 只提供公开约定、手算输入及普通回归，不提供包络实现。

## 入口与资格

在 coverage 包公开 build_priority_report(report_id, batch_id, fields) 和 sample_priority(report_id, boundary_id, segment_index, t)，会话沿用 open_archive。

fields 必须为 dict，键恰为封存批次全部 region_id，值为长度为3的 list 或 tuple，依次表示 a、b、c，函数为 ax+by+c。系数只接受非布尔整数或 Fraction，归一成 Fraction；允许零和负数。批次至多8个成员，全部外环及洞合计至多80条边，省略闭合重复点后计数。非法参数、超出边界抛 ValueError；合法但不存在的批次或报告等引用抛 KeyError。不规定同时有多种错误时的先后顺序。

原区域闭集指外环内部及边界，扣除洞的严格内部；洞边界仍属于区域。每点只比较包含该点的成员函数，取最高值并保留全部并列成员身份。面积积分忽略零面积集合。边界定位按全部保存输入的闭区域资格比较，不能只看请求段的原边来源或相邻分片。点或边接触可以造成读数跳变；函数不得与隐含的零比较。

## 报告与分片

新报告 format=2，原 format=1 报告保持原结构。新报告保留 V1 的 report_id、batch_id、binding、inputs、components、measurements、receipt，另有 priority。binding、inputs、components、measurements 与同批次普通报告对应内容相同，继续使用 V1 的分量、边界、原子段及 SourceSpan 规则，不以优先级交线重新编号原边界。

priority 恰有 fields、cells、integrals、total_integral：
- fields 是按 binding 顺序排列的列表，每项为 {"region_id":字符串,"revision":正整数,"coefficients":[a,b,c]}，三个系数都是 Fraction。
- cells 是非空列表。每项恰有 cell_id、component_id、rings、winners、integral。cell_id 为报告内唯一非空字符串；component_id 引用原联合覆盖分量。rings 为 [外环,洞,...]，环为点列表，点为两个 Fraction 的列表；不保存末尾重复闭合点，几何合法性沿用 V1，方向不限。
- winners 为非空成员引用列表，每项恰有 region_id、revision，按二者排序、去重。每片严格内域的最高函数及全部获胜成员集合必须固定，winners 恰为这个集合；恒等函数的不同成员仍分别保留。片边界上的额外并列不要求写入该片。
- integral 为该片最高函数的精确面积积分，类型为 Fraction。不同片内域互不重叠，每片归属一个原分量，全部片覆盖原联合区域至零面积差，不得落入洞或域外。允许凹片、带洞片和任意额外细分，不要求最少片数、规定片形或全新请求间的规范编号。
- integrals 按 components 顺序保存 {"component_id":字符串,"integral":Fraction}，包括积分为零的分量。total_integral 为其精确总和；同一片的并列成员不得重复累计。

sample_priority 返回恰有 point、value、winners 的独立 dict。point 沿用 sample_boundary 的点列表，value 为 Fraction，winners 格式同上，包含该点全部最高值成员。t、边界及段身份校验沿用 sample_boundary；对存在的普通报告调用 sample_priority 抛 ValueError。原 sample_boundary 也能在新报告上工作，原 sources 和端点语义保持不变。

## 绑定、发布与交付

两个构建入口共用 report_id 空间。新入口仅在同号、同批次、归一化后同系数时重放已保存成果，fields 键顺序和 list/tuple 不影响绑定；换批次、换系数或换报告种类拒绝。旧入口不能将新报告当成普通重放，反之亦然。不得自动升级或给旧成果补发优先级。

系数、固定输入、分片、积分及回执共同发布。沿用 report.before_compute、report.after_payload、report.before_commit 故障接点及异常传播；计算或发布失败不留本次报告或回执，旧成果不变。允许全量切分重算、扫描保存输入和复用已有事务，不要求索引、增量刷新、并发或崩溃恢复。

read_report、export_report、open_package 须同时支持原成果与新成果，package_version 仍为1，有理数运输沿用 {"q":[分子,分母]}。读取、采样、导出和离库核账不能重新生成包络替代保存分片；采样允许扫描保存的原始区域和系数。更正上游、修改输入 fields 或任何返回容器、关闭重开均不得改变已发布成果。

离库核账须保留 V1 核账，并核对新字段结构与引用、分片合法性及归属、无正面积重叠和漏计、获胜来源资格、同片恒等身份及最高值、分片积分和分量总账。允许对保存分片做精确几何核验与积分复算，不要求抵抗整个包被恶意一致改写，也不做密码学证明。损坏计量、漏失并列身份、无效或不合资格的获胜身份应抛 ValueError，不能信任包内 integral 或仅核对总和。

## 手算输入和核验

priority_cases.py 的六个有限案例给出原区域、系数、总积分、各分量积分、按获胜集合合计的面积，以及可沿原联合边界定位的读数。它们不约束具体切片或片序：
1. 同域单位方形 f=x、g=1-x：积分3/4，两侧各占1/2；底边中点并列。
2. 再加同域 h=x：右半保留 f、h，积分仍3/4；底边中点三方并列。
3. A 为 [0,2]² 扣除 (1/2,3/2)² 的洞，f=0；B、C 为 [1,2]×[0,2]，均为10。总面积7/2，A获胜面积3/2，B/C并列面积2，积分20；洞的左半仍无覆盖。
4. 值0和10的两个单位方形仅在(1,1)接触：两个分量积分0和10；从低值方形请求接触端点也返回10及高值成员。
5. 共边单位方形分别为-3和-1：总积分-4，共边端点读数-1，证明不能截负为零。
6. 同域直角单位三角形取 x、y、1-x-y：各获胜面积1/6，总积分11/36；三条边的中点各有两方并列。

保留全部原测试字节。交付独立核账用例及简短说明，解释分片与积分、闭区域点资格、固定绑定的交接不变量。新用例应覆盖正常反转、恒等并列、洞及接触、负值、重放冲突、失败原子性和固定交付，不要求额外产品。

运行入口：
- python3 -B priority_cases.py --fixtures 只用 V1 验证样例区域可接纳、普通面积及分量数，不验证新能力。
- python3 -B priority_cases.py --verify 在实现后运行完整原回归及公开新增用例。
- python3 -B priority_cases.py --demo 在实现后展示真实登记、优先级加工、采样、导出、源更正和磁盘重开结果。
- 原 README.md 中的完整 discover 和原 demo 均须保留并通过。

现有 .pointwise-runtime.json 的 version、kind、setup 格式沿用 README.md 中的清单。完成后使 verify 经过原回归与新业务核验，使 demo 展示新增固定交付；可直接使用上面两个新入口。任何断言失败必须非零退出，不能捕获异常后只打印成功。无需安装依赖。
