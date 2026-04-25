# lccli

一个面向 `leetcode.cn` 的命令行工具原型，支持：

- 登录当前 LeetCode CN 会话
- 获取题目并生成本地目录
- 本地运行样例
- 运行代码
- 提交代码

## 现状

这个版本优先实现了稳定链路：

- 登录不模拟账号密码输入
- 登录依赖浏览器里已经成功登录后的 Cookie
- 题目读取走 `https://leetcode.cn/graphql/`
- 运行/提交走当前前端常用接口：
  - `POST /problems/<slug>/interpret_solution/`
  - `POST /problems/<slug>/submit/`
  - `GET /submissions/detail/<id>/check/`

之所以这样做，是因为 LeetCode 登录通常带验证码、风控、短信或第三方登录流程，直接在 CLI 里模拟账号密码不稳定，长期维护成本也高。

## 安装

在仓库根目录执行：

```bash
pip install -e .
```

或者直接用模块方式运行：

```bash
python3 -m lccli --help
```

## 登录

先在浏览器中登录 `https://leetcode.cn`，然后从浏览器开发者工具里复制请求头中的 Cookie，至少应包含：

- `LEETCODE_SESSION`
- `csrftoken`

示例：

```bash
lccli login --cookie 'LEETCODE_SESSION=...; csrftoken=...'
```

也可以先保存到文件：

```bash
lccli login --cookie-file cookies.txt
```

登录成功后，配置会写到：

```text
~/.config/lccli/config.json
```

验证当前登录状态：

```bash
lccli whoami
```

## 获取题目

按题目 slug 拉取题面并生成本地模板：

```bash
lccli fetch two-sum --lang python3
```

也可以直接传题目 URL：

```bash
lccli fetch https://leetcode.cn/problems/two-sum/description/ --lang python3
```

生成结果类似：

```text
0001-two-sum/
  README.md
  README_ZH.md
  problem.json
  solution.py
```

其中：

- `README.md` 是英文题面
- `README_ZH.md` 是中文题面

## 本地测试

优先用于提交前做样例验证。当前本地测试支持 `python3` 解法，覆盖：

- 基础类型
- 数组 / 矩阵
- `ListNode`
- `TreeNode`

默认会尝试从题面里的示例提取输入和期望输出：

```bash
lccli test two-sum --file 0001-two-sum/solution.py
```

也可以手动给测试输入：

```bash
lccli test two-sum --file 0001-two-sum/solution.py --testcase $'[2,7,11,15]\n9' --expected '[0,1]'
```

如果只传 `--testcase` 不传 `--expected`，命令会执行并打印实际输出，但不会判定通过/失败。

## 运行代码

默认会读取题目的 `sampleTestCase` 作为输入：

```bash
lccli run two-sum --file 0001-two-sum/solution.py
```

也可以指定测试用例：

```bash
lccli run two-sum --file 0001-two-sum/solution.py --testcase $'[2,7,11,15]\n9'
```

或者从文件读取：

```bash
lccli run two-sum --file 0001-two-sum/solution.py --testcase-file testcase.txt
```

## 提交代码

```bash
lccli submit two-sum --file 0001-two-sum/solution.py
```

## 语言列表

查看远端支持的语言：

```bash
lccli langs
lccli langs --json
```

## 已知限制

- 目前只对 `leetcode.cn` 做了默认适配。
- 登录是 Cookie 登录，不是账号密码登录。
- 本地 `test` 目前只支持 `python3`，且主要面向常规 `Solution.method(...)` 题型。
- `run`/`submit` 依赖当前 LeetCode 前端接口；如果站点改接口，需要同步调整。
- 题目解析目前按 `slug` 或题目 URL 输入，不支持直接输入题号。
- 题面会原样写入 Markdown，HTML 内容未做深度清洗。

## 后续建议

如果你要把它继续做成可长期使用的 CLI，下一步建议按这个顺序继续：

1. 加入 `browser login`，通过本地浏览器打开登录页，再回收 Cookie。
2. 加入 `题号 -> slug` 的本地缓存索引。
3. 加入 `test` 子命令，支持本地样例执行。
4. 把返回结果整理成更友好的终端输出。
5. 为常见语言生成更完整的本地工程模板。

