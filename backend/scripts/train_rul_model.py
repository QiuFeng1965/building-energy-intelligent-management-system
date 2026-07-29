# train_rul_model.py
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import joblib

print("🚀 正在初始化物理劣化模拟数据...")

# 1. 生成模拟的设备传感器历史数据 (1000条样本)
np.random.seed(42)
n_samples = 1000

# 特征1：振动有效值 (Vibration RMS, 正常 1~4，异常 5~10)
vibration = np.random.uniform(1.0, 10.0, n_samples)
# 特征2：温度残差 (Temp Offset, 正常 0~3，异常 4~15)
temp_offset = np.random.uniform(0.0, 15.0, n_samples)
# 特征3：电流波动率 (Current Fluctuation, 正常 1~5，异常 6~12)
current_fluctuation = np.random.uniform(1.0, 12.0, n_samples)

# 2. 定义 RUL（剩余寿命，单位：天）的衰减逻辑
# 物理逻辑：振动越大、温度越高、电流波动越大，剩余寿命越短
# 假设全新设备寿命为 365 天
rul = 365 - (vibration * 20) - (temp_offset * 10) - (current_fluctuation * 5)
# 加上一点随机高斯白噪声，让数据更真实
rul = rul + np.random.normal(0, 5, n_samples)
rul = np.clip(rul, 1, 365) # 限制寿命在 1 到 365 天之间

# 组装成 DataFrame
data = pd.DataFrame({
    'vibration_rms': vibration,
    'temp_offset': temp_offset,
    'current_fluctuation': current_fluctuation,
    'RUL': rul
})

X = data[['vibration_rms', 'temp_offset', 'current_fluctuation']]
y = data['RUL']

# 划分训练集和测试集
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print("🧠 正在训练 Random Forest 预测模型...")
# 3. 训练随机森林回归模型
model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
model.fit(X_train, y_train)

# 评估模型
predictions = model.predict(X_test)
rmse = np.sqrt(mean_squared_error(y_test, predictions))
print(f"✅ 模型训练完成！测试集 RMSE: {rmse:.2f} 天")

# 4. 导出为 .pkl 模型文件
model_filename = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'rul_prediction_model.pkl')
joblib.dump(model, model_filename)
print(f"📦 真实机器学习模型已保存为: {model_filename}")