# VS Code 使用说明

本模板已经配置好 VS Code 的 LaTeX Workshop 编译规则。推荐所有队员使用同一个项目文件夹，避免每个人的编译方式不一致。

## 一、每位队员需要安装

1. VS Code
2. VS Code 插件：LaTeX Workshop
3. LaTeX 发行版：MiKTeX 或 TeX Live

Windows 新手推荐使用 MiKTeX。安装 MiKTeX 后，如果编译时提示缺少宏包，选择自动安装即可。

## 二、打开方式

在 VS Code 中选择：

```text
File -> Open Folder
```

然后打开整个文件夹，而不是只打开单个 tex 文件：

```text
CUMCM-LaTeX-Template-main
```

主文件是：

```text
template.tex
```

## 三、编译方式

打开 `template.tex` 后，点击 VS Code 左侧的 TeX 图标，选择：

```text
Build LaTeX project
```

默认使用：

```text
xelatex -> bibtex -> xelatex*2
```

如果暂时没有参考文献，也可以使用单次：

```text
xelatex
```

## 四、必须使用 XeLaTeX

本模板是中文论文模板，请使用 XeLaTeX 编译。不要使用 pdfLaTeX。

如果 VS Code 报错找不到 `xelatex`，说明 LaTeX 发行版没有加入系统 PATH。可以关闭并重新打开 VS Code，或者重新安装 MiKTeX / TeX Live，并勾选加入 PATH。

## 五、文件放置建议

- 正文：写在 `template.tex`
- 图片：放在 `figures/`
- 代码：放在 `code/`
- 模板类文件：`cumcmthesis.cls` 不建议随意修改
- 参考文献：如需使用 BibTeX，可创建 `ref.bib`

## 六、发给队友时

直接把整个 `CUMCM-LaTeX-Template-main` 文件夹压缩发给队友。不要只发 `template.tex`，否则图片、代码、模板类文件和 VS Code 配置可能缺失。

每位队友本机仍然需要安装 MiKTeX 或 TeX Live。宏包不是由 VS Code 提供的，而是由 LaTeX 发行版提供的。
