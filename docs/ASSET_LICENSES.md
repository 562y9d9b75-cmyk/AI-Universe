# 3D 资产与授权

本次交付的建模脚本、场景几何、材质参数和 oak albedo 像素均为本项目原创，无第三方素材、人物照片或付费资产。

| 文件 | 内容 | 授权 |
| --- | --- | --- |
| assets/headquarters.blend | 可编辑模块化场景：大厅、工位、会议区、咖啡台、休闲书架、绿植、隔断、装饰 | CC0-1.0 |
| frontend/public/assets/headquarters.glb | 经静态批处理优化的 PBR 楼层 | CC0-1.0 |
| frontend/public/assets/workstation.glb | 可复用工位模块 | CC0-1.0 |
| scripts/build_assets.py | Blender 场景生成脚本 | 随项目 MIT |
| scripts/optimize_assets.py | 按材质合并静态网格，保留源 blend | 随项目 MIT |

原创资产按 CC0 1.0 Universal 贡献给公有领域：https://creativecommons.org/publicdomain/zero/1.0/ 。仅适用于上表列出的原创资产；软件依赖各自的许可证不改变。

重建（需要 Blender 4.3 或兼容版本）：

```sh
blender -b -t 2 -P scripts/build_assets.py
blender -b -t 2 -P scripts/optimize_assets.py
```

尺度单位为米；源文件 Z-up，GLB 导出为 glTF 标准坐标。glTF 使用可导出的金属度/粗糙度 PBR 材质和内嵌原创木纹贴图。当前家具是独立模块，静态总部合并为 20 个材质批次，避免大量键盘按键等独立物体产生过多绘制调用。

**未交付**：写实员工模型、不同人物面部/服装/发型、皮肤与毛发材质、骨骼绑定、生活动作和动画混合状态机。页面显示的字母头像和工位标记是管理控件，不作为写实人物资产交付，也不说明人物已制作。

## 写实人物的接入接口（资产待交付）

`frontend/components/EmployeeModel.tsx` 已预留 GLB 骨骼动画的交叉渐变、生活状态与走动路径。它只消费独立生活状态，不写任务状态。清单 `frontend/public/assets/manifest.json` 当前 `employees` 为空，因此实际产品没有人物，也不能把接口代码当作人物动画验收通过。

未来每个 `employees` 条目包含独立的 `name`、本机 `/assets/employees/...glb` 路径、`license` 和 `clips`（idle/typing/coffee/walking/reading/meeting/whiteboard/resting/returning 到真实 GLB clip 名的映射）。加载器拒绝重复模型 URI、路径穿越和没有授权说明的条目。必须自行核验人物比例、独立外观、动画完整性及素材授权，再填入清单；当前未下载任何身份不明素材。
