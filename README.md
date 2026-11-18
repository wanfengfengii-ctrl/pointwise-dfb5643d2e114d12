# 海岬平面观测覆盖归档 V1

Python 3.11 标准库工程。坐标为局部平面米制坐标，面积为平方米；逐段长度平方单位也是平方米，不表示总周长的平方。没有网络服务或安装依赖。

资料员登记测线区域及更正，指定明确修订封存当天批次；质控员加工联合覆盖；采样员沿真实边界定位复测点；交付员导出固定包，次日外业人员可离库核账。保存的报告不随源更正改变。

从项目根目录运行：

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B -m tests.test_delivery --demo
```

demo读取examples中的实际输入和独立手算预期，在测试临时目录创建SQLite归档，执行登记、封存、覆盖、采样、导出、更正及关闭重开；断言后打印POINTWISE_SCENARIO。运行清单为.pointwise-runtime.json。所有写入仅在调用者指定归档或测试临时目录。

## 公开接口

```python
from fractions import Fraction
from coverage import (open_archive, put_region, seal_batch, build_report,
                      sample_boundary, read_report, export_report, open_package)

with open_archive('observations.sqlite'):
    revision = put_region('line-A', [(0,0),(4,0),(4,3),(0,3)], [])
    seal_batch('day', [('line-A', revision)])
    report = build_report('quality', 'day')
    boundary = report['components'][0]['boundaries'][0]
    sample = sample_boundary('quality', boundary['boundary_id'], 0, Fraction(1,3))
    package = export_report('quality')
offline = open_package(package)
```

open_archive是会话上下文；嵌套会话退出恢复外层会话。单会话单进程写入，不支持嵌套写事务。重复打开只检查模式，不重置用户资料；未知版本或不兼容模式抛ValueError，不自动迁移。Archive.connection提供SQLite连接用于运维检查；业务写入应使用公开入口。

put_region每次合法调用均新建递增修订，相同内容也新增。输入整数或Fraction，拒绝浮点、布尔值和空值。环可带一个末尾闭合点；保留输入方向、共线中间顶点及原边编号。禁止零面积、零长边、自交、非相邻接触和相邻回折；洞须严格在外环内且彼此不接触、不相交、不嵌套。非法输入ValueError且不占修订号。coverage.revisions的get_revision和get_current_revision可读取不可变修订值对象。

seal_batch接收非空(region_id, revision)集合，同一区域不可重复；按身份排序。同号同集合重放，异集合ValueError，缺修订KeyError；成员、绑定和封存一起提交，不暴露半批次。返回SealedBinding含明确成员及不可变几何快照。

build_report仅消费封存批次，报告同号同批次固定重放、异批次ValueError、缺批次KeyError。处理精确交点和共线重合，采用联合覆盖；正长度邻接连接内域，点接触不连接。片段两侧使用不跨任何边的精确有理见证分类，不依赖epsilon或浮点角度。保留交点、原端点及来源变化处的原子切分。外环逆时针、洞顺时针，覆盖在左。内部边删除，重合外露段只输出一次并保留全部来源。

报告为独立嵌套dict/list，包含format、report_id、batch_id、binding、inputs、components、measurements、receipt。components中的每个分量有component_id和boundaries；每个边界有boundary_id和segments；每段含start、end及sources。来源字段region_id/revision/ring_index/edge_index标识原始输入边，t0/t1是有向参数。所有几何量为Fraction。分量和边界有确定编号，段序号从0开始，读取不重新编号。measurements含areas、total_area及boundary逐段length_squared。receipt与报告共同发布。

sample_boundary的t严格为[0,1]中的Fraction，非法参数ValueError；未知报告、边界、段KeyError。返回point和sources，各来源附parameter；端点仍采用请求段来源。只从保存报告取点，反向原边按保存参数区间插值，不执行覆盖加工。

read_report缺报告KeyError，残缺记录ValueError，不以重算掩盖损坏；返回值及所有嵌套容器与保存状态隔离。读取会重算保存闭环的计量并核对固定原边来源。export_report输出确定性JSON字符串，open_package无需数据库返回独立报告。外层package_version=1及report；报告format=1。有理数以对象{"q":[分子,分母]}运输，分母正且最简，其他身份整数仍为JSON整数。拒绝重复键、未知版本、缺输入/来源/计量、悬空身份、错误参数及不一致计量。离库核账不重新计算联合覆盖，不声称可抵抗任意恶意一致改写。

发布使用单个SQLite事务。Archive.failure_hook可设置为(name, connection)回调，用于确定性故障演练；接点revision.before_commit、batch.before_commit、report.before_compute、report.after_payload、report.before_commit。回调异常原样传播，事务回滚，旧成果不变；清除回调后可以原号重试。

## 模块职责和回归

regions/rings/region_validation/revisions管理合法输入和固定修订；members/bindings/sealing/batches管理明确封存。intersections/segments/arrangement/coverage_union进行精确平面加工，areas/boundary_measure/reports/sampling消费同一边界。schema/database/publication/result_codec拥有共同发布和保存表示；reading/exporting/package_reader/reconciliation完成固定读取与离库核账。

原业务场景：test_coverage覆盖重叠、分数交点、包含、点/边接触、洞和填洞、排列确定性及整数格独立面积参照；test_intake覆盖非法输入、修订连续性、缺引用回滚和固定绑定；test_sampling覆盖重合来源、反向原边参数及端点；test_publication覆盖真实SQL失败、重放、计算异常及初始化；test_delivery覆盖嵌套容器隔离、更正与重开、残缺包拒绝及普通平面范围。手算日样例面积12+12-4=20，底边1/3处为(4/3,0)。

V1仅支持平面普通闭环，不执行周期坐标识别、球面几何、空间索引、在线增量刷新或并发服务。
