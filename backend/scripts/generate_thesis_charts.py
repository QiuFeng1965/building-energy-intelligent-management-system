# -*- coding: utf-8 -*-
"""
擎翼数字中枢 - 论文专属高颜值数据可视化出图脚本
生成图表自动对齐：建筑科技蓝 (RGB: 30, 58, 138) 与 智能绿 配色
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

# 1. 全局样式美化设置（对齐你的文档视觉规范）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS'] # 支持中文展示
plt.rcParams['axes.unicode_minus'] = False
sns.set_theme(style="whitegrid")

# 定义项目标准主色调
TECH_BLUE = '#1E3A8A'  # 建筑科技蓝
SMART_GREEN = '#10B981' # 智能绿
WARN_ORANGE = '#F59E0B' # 警告橙

print("🚀 正在读取/模拟孪生事实数仓数据并生成论文图表...")

# 2. 模拟/构建符合数据字典的 5000 条核心预处理样本
np.random.seed(42)
n_samples = 5000

# 构造原始高维特征（存在多重共线性）
vibration = np.random.uniform(1.0, 10.0, n_samples)
temp_offset = np.random.uniform(0.0, 15.0, n_samples)
current_fluct = np.random.uniform(1.0, 12.0, n_samples)
# 注入物理耦合共线性特征
ambient_temp = np.random.uniform(15.0, 38.0, n_samples)
chilled_water_temp = ambient_temp * 0.3 + np.random.normal(7, 0.5, n_samples) 
power_load = (vibration * 15) + (temp_offset * 8) + np.random.normal(50, 10, n_samples)

df = pd.DataFrame({
    'vibration_rms': vibration,
    'temp_offset': temp_offset,
    'current_fluctuation': current_fluct,
    'ambient_temperature': ambient_temp,
    'chilled_water_temp': chilled_water_temp,
    'power_load_kws': power_load
})

# ==========================================================
# 图 1：特征选择前后的数量变化（直方/条形图）- 对应论文 3.5 节
# ==========================================================
plt.figure(figsize=(7, 4.5))
stages = ['物联网原始报文特征', 'DataAuditor质量清洗后', '皮尔逊/卡方特征选择后', 'PCA降维压缩特征']
feature_counts = [18, 14, 6, 3] # 对应你的设计逻辑

bars = plt.bar(stages, feature_counts, color=[TECH_BLUE, '#3B82F6', SMART_GREEN, '#6EE7B7'], width=0.5, edgecolor='k', alpha=0.9)
plt.title('3-3 预处理各阶段特征空间维度(数量)收缩对比', fontsize=12, fontweight='bold', pad=15)
plt.ylabel('特征变量数量 (个)', fontsize=10)
plt.ylim(0, 22)
plt.grid(axis='y', linestyle='--', alpha=0.5)

# 添加数字标签
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2.0, yval + 0.5, f'{int(yval)}个', ha='center', va='bottom', fontsize=10, fontweight='bold')

plt.tight_layout()
plt.savefig('feature_dimension_shrink.png', dpi=300)
print("✅ 图 1 已成功保存为: feature_dimension_shrink.png")
plt.close()


# ==========================================================
# 图 2：数据转换标准化前后数据分布对比 - 对应论文 3.2 & 3.5 节
# ==========================================================
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

# 原始数据分布（以绝对值极大的耗电负载为例，右偏严重或尺度极大）
sns.histplot(df['power_load_kws'], kde=True, ax=axes[0], color=WARN_ORANGE, edgecolor='k', alpha=0.6)
axes[0].set_title('(a) 原始机电设备负载耗电量特征分布 (大尺度量纲)', fontsize=11, fontweight='bold')
axes[0].set_xlabel('Power Load (kW/h)')
axes[0].set_ylabel('频数 (Frequency)')

# Z-score 标准化后的标准正态分布
scaler = StandardScaler()
scaled_features = scaler.fit_transform(df[['power_load_kws']])
sns.histplot(scaled_features.flatten(), kde=True, ax=axes[1], color=TECH_BLUE, edgecolor='k', alpha=0.7)
axes[1].set_title('(b) Z-score 标准化后特征分布 (均值0, 方差1)', fontsize=11, fontweight='bold')
axes[1].set_xlabel('Standardized Value (无量纲)')
axes[1].set_ylabel('频数 (Frequency)')

plt.suptitle('图 3-1 机电核心连续型能耗特征标准化前后分布转换对比', fontsize=13, fontweight='bold', y=0.98)
plt.tight_layout()
plt.savefig('data_distribution_comparison.png', dpi=300)
print("✅ 图 2 已成功保存为: data_distribution_comparison.png")
plt.close()


# ==========================================================
# 图 3：PCA 降维效果散点图 - 对应论文 3.4 节
# ==========================================================
# 提取所有连续型特征进行标准化和 PCA
X_numeric = df.values
X_scaled = scaler.fit_transform(X_numeric)

pca = PCA(n_components=2) # 提取前两个主成分用于二维平面画图
X_pca = pca.fit_transform(X_scaled)
explained_variance = pca.explained_variance_ratio_

# 模拟一个异常运行状态分类作为色彩分类标签
y_anomaly = (df['vibration_rms'] > 6.5) | (df['temp_offset'] > 9.0)

plt.figure(figsize=(8, 5.5))
scatter = plt.scatter(
    X_pca[:, 0], X_pca[:, 1], 
    c=y_anomaly, 
    cmap=plt.cm.get_cmap('coolwarm'), 
    alpha=0.75, s=25, edgecolor='k', linewidth=0.3
)

plt.title(f'图 3-2 PCA 降维演进散点图\n(前两个主成分累计方差贡献率: {sum(explained_variance)*100:.2f}%)', fontsize=12, fontweight='bold', pad=12)
plt.xlabel(f'主成分 1 (PC1 - 方差贡献: {explained_variance[0]*100:.2f}%)', fontsize=10)
plt.ylabel(f'主成分 2 (PC2 - 方差贡献: {explained_variance[1]*100:.2f}%)', fontsize=10)

# 添加图例
cbar = plt.colorbar(scatter, ticks=[0, 1])
cbar.ax.set_yticklabels(['正常状态 (NORMAL)', '劣化异常 (ABNORMAL)'], fontproperties='SimHei', fontsize=9)
plt.grid(True, linestyle=':', alpha=0.6)

plt.tight_layout()
plt.savefig('pca_dimension_reduction.png', dpi=300)
print("✅ 图 3 已成功保存为: pca_dimension_reduction.png")
plt.close()

print("\n🎉 全套论文高质感插图已生成完毕！快去文件夹里看看吧！")