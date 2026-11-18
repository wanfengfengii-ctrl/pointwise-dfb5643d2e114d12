# 复测优先级交接不变量说明

本说明面向交付与离库核账，解释 format=2 报告的三组交接不变量。公开契约见 PRIORITY.md，
手算样例见 priority_cases.py，独立核账用例见 tests/test_priority.py。新增实现模块：
priority_fields（系数归一与闭区域资格）、priority_geometry（精确竖条分解与面积矩）、
priority_cells（分片与积分）、priority_validation（结构校验与几何核账）、
priority_reports（构建入口）、priority_sampling（边界读数）。

## 一、分片与积分

- priority.cells 把每个原联合覆盖分量切成内域互不重叠的片；全部片合起来覆盖原联合区域，
  至多差零面积集合；片不落入洞或域外。允许凹片、带洞片和任意额外细分。
- 每片严格内域上最高函数固定、获胜成员集合固定，winners 恰为该集合；同片并列成员的
  仿射函数恒等，恒等函数的不同成员分别保留；片边界上的额外并列不写入该片。
- 每片 integral 是获胜共同函数在该片上的精确有理面积积分；同片并列成员只计量一次。
- integrals 按 components 顺序给出各分量积分（含积分为零的分量），total_integral 为其精确总和。
- 核账逐片重算面积矩与积分，再核对分量账与总账；不信任包内任何 integral 字段本身。

## 二、闭区域点资格

- 成员闭区域 = 外环内部及边界，扣除洞的严格内部；洞边界仍属于区域。
- 每点只比较闭区域覆盖该点的成员函数，取最高值并保留全部并列身份；不与隐含的零比较，
  负值照常参与；点或边接触可造成读数跳变。
- sample_priority 按全部保存输入的闭区域判定资格，不看请求段的原边来源，也不看相邻分片。
- 读取、采样、导出、离库核账只使用保存的分片、保存的原始区域和系数，不重新生成包络。

## 三、固定绑定与发布

- build_report 与 build_priority_report 共用 report_id 空间；同号、同批次、归一化后同系数
  才重放（fields 键顺序和 list/tuple 不影响绑定）；换批次、换系数、换报告种类一律拒绝；
  不自动升级旧成果，也不给旧成果补发优先级。
- 系数、固定输入、分片、积分与回执在同一 SQLite 事务发布；report.before_compute、
  report.after_payload、report.before_commit 接点异常原样传播并回滚，不留本次报告或回执，
  旧成果不变，清除回调后可原号重试。
- 更正上游、修改输入 fields 或任何返回容器、关闭重开，均不改变已发布成果。
- 离库核账保留 V1 全部核对，并新增：priority 结构与引用、分片几何合法性与归属分量、
  片间无正面积重叠、分量覆盖无漏计、获胜身份资格与恒等、最高值不被其他成员超过、
  逐片积分与分量总账。损坏计量、漏失并列身份、无效或不合资格的获胜身份均抛 ValueError。

## 运行

- python3 -B -m unittest discover -s tests -p 'test_*.py' -v （原回归 + 新增独立用例）
- python3 -B -m tests.test_delivery --demo （原 V1 演示）
- python3 -B priority_cases.py --fixtures|--verify|--demo （样例接纳、全量核验、新增演示）
