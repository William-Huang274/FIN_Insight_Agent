# FIN 0.1.3 S1 bounded semantic-anchor clean proof

- 日期：2026-08-10
- implementation：`0ac314f2f96db3a262505bca75012cd7a88a5b76`
- proof digest：`b8a9b04d6ac4b349b40e6fc635b881da0bdcf0a0ca6162a373dc9a91af74bd04`
- corrected Pack digest：`5ba1091ddc71d0c8543f186e4331bf2caae7d10e365af0a0f7510a056b5e9984`
- 网络／模型／retry：`0／0／0`

## 结果

两个独立 Git archive、两个 fresh Python process 各自补入三份 digest-bound private inputs：原始 22-Evidence Pack、Dell Reader response、Micron Reader response。两边输出逐字节一致：Dell `3/3`、Micron `2/2` fragments，Pack=`22→27 Evidence／15→14 gaps`，core/supplier/valuation-input=`true/true/true`。

真实长文档与 synthetic mutation 同时通过：旧 regex surface 静态拒绝；重复 demand/supply、文档尾部同名词不改变局部业务窗口；anchor 缺失、窗口真实过宽和最终 excerpt 过大分别保留不同 failure code。历史 source result `9be7ec13...e18920` 未修改，也没有重新请求来源。

## 下一步与边界

proof 证明 compiler 和 corrected Pack 可从 clean source 重现，但当前 proof 文件本身尚未提交，持久化 corrected Pack 也尚未发生。下一步提交并推送 proof，再在 clean/synced head 上运行零网络 materializer；只有公开 result 继续保持 core=true，才进入一次独立模型 authority 和 changed-input DeepSeek 报告比较。
