// frontend/src/config/BuildingLibrary.js
// 智慧校园建筑几何体库 (保留完美布局 + 独立小方块窗户 + 真实屋顶结构 + 路网绿化 + 路灯围栏人工湖)

export const buildingMaterials = {
  detailMaterial: {
    metalness: 0.1,       
    roughness: 0.85,      
    transparent: false,   
  },
  wireframeMaterial: {
    transparent: true,
    opacity: 0.85,        
    blending: 1,          
    depthWrite: false, 
  }
}

// ==========================================
// 🌟 核心引擎 1：自动生成主体墙面 + 独立小方块窗户 + 楼顶结构
// ==========================================
function generateBuildingWithWindows(w, h, d, offsetX = 0, offsetY = 0, offsetZ = 0) {
  const parts = [];
  parts.push({ type: 'TresBoxGeometry', args: [w, h, d], position: [offsetX, offsetY, offsetZ], isWall: true });

  const winW = 1.2, winH = 2.0, winD = 0.4, gapX = 3.5, gapY = 4.0;
  const startX = -w / 2 + 2.0, endX = w / 2 - 2.0;
  const startZ = -d / 2 + 2.0, endZ = d / 2 - 2.0;
  const startY = -h / 2 + 2.5, endY = h / 2 - 1.5;

  for (let y = startY; y <= endY; y += gapY) {
    for (let x = startX; x <= endX; x += gapX) {
      parts.push({ type: 'TresBoxGeometry', args: [winW, winH, winD], position: [offsetX + x, offsetY + y, offsetZ + d / 2], isWindow: true });
      parts.push({ type: 'TresBoxGeometry', args: [winW, winH, winD], position: [offsetX + x, offsetY + y, offsetZ - d / 2], isWindow: true });
    }
    for (let z = startZ; z <= endZ; z += gapX) {
      parts.push({ type: 'TresBoxGeometry', args: [winD, winH, winW], position: [offsetX + w / 2, offsetY + y, offsetZ + z], isWindow: true });
      parts.push({ type: 'TresBoxGeometry', args: [winD, winH, winW], position: [offsetX - w / 2, offsetY + y, offsetZ + z], isWindow: true });
    }
  }

  const roofY = offsetY + h / 2 + 0.5;
  const thick = 0.8;
  parts.push({ type: 'TresBoxGeometry', args: [w, 1, thick], position: [offsetX, roofY, offsetZ + d / 2 - thick / 2], isWall: true });
  parts.push({ type: 'TresBoxGeometry', args: [w, 1, thick], position: [offsetX, roofY, offsetZ - d / 2 + thick / 2], isWall: true });
  parts.push({ type: 'TresBoxGeometry', args: [thick, 1, d - thick * 2], position: [offsetX + w / 2 - thick / 2, roofY, offsetZ], isWall: true });
  parts.push({ type: 'TresBoxGeometry', args: [thick, 1, d - thick * 2], position: [offsetX - w / 2 + thick / 2, roofY, offsetZ], isWall: true });
  parts.push({ type: 'TresBoxGeometry', args: [w * 0.3, 2.5, d * 0.4], position: [offsetX, roofY + 0.75, offsetZ], isWall: true });

  return parts;
}

// ==========================================
// 🌟 核心引擎 2：路网、树木、路灯生成器
// ==========================================
// ==========================================
// 🌟 核心引擎 2：路网、树木、路灯生成器 (深度科幻升级版)
// ==========================================
function generateRoadsAndTrees() {
  const elements = [];
  const roadW = 8;     

  // --- 1. 智慧全息路网生成器 ---
  const createSmartRoad = (l, w, x, z, isXAxis) => {
    const roadY = 0.05;
    // 底层暗黑沥青路面
    elements.push({ type: 'TresBoxGeometry', args: isXAxis ? [l, roadY, w] : [w, roadY, l], position: [x, roadY/2, z], isTrack: true });
    
    // 中央全息数据流 (发光中轴线)
    elements.push({ type: 'TresBoxGeometry', args: isXAxis ? [l, 0.02, 0.3] : [0.3, 0.02, l], position: [x, roadY + 0.01, z], isWindow: true });
    
    // 两侧微光轮廓边线
    if(isXAxis) {
        elements.push({ type: 'TresBoxGeometry', args: [l, 0.02, 0.1], position: [x, roadY + 0.01, z + w/2 - 0.4], isWindow: true });
        elements.push({ type: 'TresBoxGeometry', args: [l, 0.02, 0.1], position: [x, roadY + 0.01, z - w/2 + 0.4], isWindow: true });
    } else {
        elements.push({ type: 'TresBoxGeometry', args: [0.1, 0.02, l], position: [x + w/2 - 0.4, roadY + 0.01, z], isWindow: true });
        elements.push({ type: 'TresBoxGeometry', args: [0.1, 0.02, l], position: [x - w/2 + 0.4, roadY + 0.01, z], isWindow: true });
    }
  }

  // 铺设横向与纵向干道
  createSmartRoad(180, roadW, -15, -22.5, true);
  createSmartRoad(180, roadW, -15, 22.5, true);
  createSmartRoad(110, roadW, 22.5, 0, false);
  createSmartRoad(110, roadW, -22.5, 0, false);
  createSmartRoad(110, roadW, -67.5, 0, false);

  // --- 2. 🌲 核心细节：低多边形全息树阵列生成器 ---
  const addTrees = (startX, endX, startZ, endZ, count) => {
    const stepX = count > 1 ? (endX - startX) / (count - 1) : 0;
    const stepZ = count > 1 ? (endZ - startZ) / (count - 1) : 0;
    for (let i = 0; i < count; i++) {
      const x = startX + stepX * i;
      const z = startZ + stepZ * i;
      
      // ① 树干 (深色金属基座)
      elements.push({ type: 'TresCylinderGeometry', args: [0.15, 0.25, 1.5, 6], position: [x, 0.75, z], isWall: true });
      
      // ② 底部投影光环 (仿佛树木是从地下数据管网中投影出来的)
      elements.push({ type: 'TresCylinderGeometry', args: [1.2, 1.2, 0.05, 16], position: [x, 0.05, z], isWindow: true });

      // ③ 全息树冠层 (低多边形/钻石切面风格，利用极少边数的球体模拟晶体结构)
      // 外层：透明数字外壳 
      elements.push({ type: 'TresSphereGeometry', args: [1.8, 5, 4], position: [x, 3.2, z], isGlass: true });
      // 中层：次级几何体，增加切面错位感
      elements.push({ type: 'TresSphereGeometry', args: [1.2, 4, 3], position: [x, 3.0, z], isGlass: true });
      // ④ 内核：高亮发光数据核
      elements.push({ type: 'TresSphereGeometry', args: [0.5, 8, 8], position: [x, 3.2, z], isWindow: true });
    }
  };

  // --- 3. 赛博朋克路灯阵列 ---
  const addStreetlights = (startX, endX, startZ, endZ, count, isZAxis) => {
    const stepX = count > 1 ? (endX - startX) / (count - 1) : 0;
    const stepZ = count > 1 ? (endZ - startZ) / (count - 1) : 0;
    for (let i = 0; i < count; i++) {
      const x = startX + stepX * i;
      const z = startZ + stepZ * i;
      
      // 灯杆底座
      elements.push({ type: 'TresCylinderGeometry', args: [0.3, 0.4, 0.8, 8], position: [x, 0.4, z], isWall: true });
      // 科技感立杆
      elements.push({ type: 'TresCylinderGeometry', args: [0.1, 0.15, 5.5, 8], position: [x, 3.5, z], isWall: true });
      // 杆身发光装饰环/灯带
      elements.push({ type: 'TresCylinderGeometry', args: [0.12, 0.12, 1.5, 8], position: [x, 3.5, z], isWindow: true });
      
      // 悬挑灯头支撑臂
      const lampArmPos = isZAxis ? [x - 0.6, 6, z] : [x, 6, z - 0.6];
      elements.push({ type: 'TresBoxGeometry', args: isZAxis ? [1.2, 0.1, 0.2] : [0.2, 0.1, 1.2], position: lampArmPos, isWall: true });
      // 发光灯组核心
      const lightPos = isZAxis ? [x - 0.8, 5.95, z] : [x, 5.95, z - 0.8];
      elements.push({ type: 'TresBoxGeometry', args: isZAxis ? [0.6, 0.1, 0.4] : [0.4, 0.1, 0.6], position: lightPos, isWindow: true });
    }
  };

  // 执行种树 (沿道路两侧与广场周边)
  addTrees(-80, 50, -18, -18, 16); 
  addTrees(-80, 50, -27, -27, 16);
  addTrees(-80, 50, 18, 18, 16);   
  addTrees(-80, 50, 27, 27, 16);   
  addTrees(-18, 18, -18, -18, 6);
  addTrees(-18, 18, 18, 18, 6);
  addTrees(-18, -18, -18, 18, 6);
  addTrees(18, 18, -18, 18, 6);

  // 执行立灯 (交错排布)
  addStreetlights(-75, 45, -17, -17, 8, false);
  addStreetlights(-75, 45, 28, 28, 8, false);
  addStreetlights(-21, -21, -45, 45, 6, true);
  addStreetlights(21, 21, -45, 45, 6, true);

  return elements;
}


// ==========================================
// 2. 具体场景建模函数 (完全合并您的数据)
// ==========================================
export function defineBuildings() {
  return [
    // ================== 中心景观 ==================
    {
      id: "B7", name: "公共广场与喷泉", type: "景观", status: "正常", color: "#94a3b8",
      position: [0, 0, 0], scale: [40, 1, 40], 
      group: [
        // ================== 1. 广场多层基座 ==================
        // 最底层方形广场基座
        { type: 'TresBoxGeometry', args: [40, 0.2, 40], position: [0, 0.1, 0], isGround: true },
        // 中层巨大圆形集散广场
        { type: 'TresCylinderGeometry', args: [18, 18, 0.2, 64], position: [0, 0.2, 0], isGround: true },

        // ================== 2. 全息能量喷泉水池 ==================
        // 喷泉外圈金属池壁
        { type: 'TresCylinderGeometry', args: [10, 10, 0.6, 64], position: [0, 0.4, 0], isWall: true },
        // 喷泉内圈能量水面 (利用 isGlass 的深邃发光特性模拟科幻液态能量)
        { type: 'TresCylinderGeometry', args: [9.2, 9.2, 0.6, 64], position: [0, 0.45, 0], isGlass: true },

        // ================== 3. 喷泉中央：悬浮能量核心 ==================
        // 中央科技底座
        { type: 'TresCylinderGeometry', args: [3, 4, 1.5, 32], position: [0, 1.2, 0], isWall: true },
        // 向上延伸的主轴天线
        { type: 'TresCylinderGeometry', args: [0.8, 0.8, 4, 16], position: [0, 3.5, 0], isWall: true },
        // 悬浮在主轴周围的金属光环
        { type: 'TresCylinderGeometry', args: [4, 4, 0.2, 32], position: [0, 3.0, 0], isWall: true },
        { type: 'TresCylinderGeometry', args: [2.5, 2.5, 0.2, 32], position: [0, 4.5, 0], isWall: true },
        // 顶端的全息发光能量球 (视觉焦点)
        { type: 'TresSphereGeometry', args: [2.2, 32, 32], position: [0, 6.2, 0], isWindow: true },

        // ================== 4. 广场四角阵列：科技方尖碑 ==================
        // 东南角碑
        { type: 'TresBoxGeometry', args: [2, 0.4, 2], position: [14, 0.4, 14], isWall: true },
        { type: 'TresBoxGeometry', args: [0.6, 5, 0.6], position: [14, 2.5, 14], isWindow: true }, // 发光柱体
        { type: 'TresBoxGeometry', args: [1.2, 0.4, 1.2], position: [14, 5.2, 14], isWall: true }, // 金属顶帽
        // 西南角碑
        { type: 'TresBoxGeometry', args: [2, 0.4, 2], position: [-14, 0.4, 14], isWall: true },
        { type: 'TresBoxGeometry', args: [0.6, 5, 0.6], position: [-14, 2.5, 14], isWindow: true }, 
        { type: 'TresBoxGeometry', args: [1.2, 0.4, 1.2], position: [-14, 5.2, 14], isWall: true }, 
        // 东北角碑
        { type: 'TresBoxGeometry', args: [2, 0.4, 2], position: [14, 0.4, -14], isWall: true },
        { type: 'TresBoxGeometry', args: [0.6, 5, 0.6], position: [14, 2.5, -14], isWindow: true }, 
        { type: 'TresBoxGeometry', args: [1.2, 0.4, 1.2], position: [14, 5.2, -14], isWall: true }, 
        // 西北角碑
        { type: 'TresBoxGeometry', args: [2, 0.4, 2], position: [-14, 0.4, -14], isWall: true },
        { type: 'TresBoxGeometry', args: [0.6, 5, 0.6], position: [-14, 2.5, -14], isWindow: true }, 
        { type: 'TresBoxGeometry', args: [1.2, 0.4, 1.2], position: [-14, 5.2, -14], isWall: true }, 

        // ================== 5. L型边缘生态花坛与座椅 ==================
        // 东南花坛
        { type: 'TresBoxGeometry', args: [6, 0.8, 2], position: [14, 0.5, 8], isWall: true },
        { type: 'TresBoxGeometry', args: [2, 0.8, 6], position: [8, 0.5, 14], isWall: true },
        { type: 'TresBoxGeometry', args: [5.6, 0.2, 1.6], position: [14, 0.9, 8], isGrass: true }, // 内部绿植
        { type: 'TresBoxGeometry', args: [1.6, 0.2, 5.6], position: [8, 0.9, 14], isGrass: true },
        // 西南花坛
        { type: 'TresBoxGeometry', args: [6, 0.8, 2], position: [-14, 0.5, 8], isWall: true },
        { type: 'TresBoxGeometry', args: [2, 0.8, 6], position: [-8, 0.5, 14], isWall: true },
        { type: 'TresBoxGeometry', args: [5.6, 0.2, 1.6], position: [-14, 0.9, 8], isGrass: true },
        { type: 'TresBoxGeometry', args: [1.6, 0.2, 5.6], position: [-8, 0.9, 14], isGrass: true },
        // 东北花坛
        { type: 'TresBoxGeometry', args: [6, 0.8, 2], position: [14, 0.5, -8], isWall: true },
        { type: 'TresBoxGeometry', args: [2, 0.8, 6], position: [8, 0.5, -14], isWall: true },
        { type: 'TresBoxGeometry', args: [5.6, 0.2, 1.6], position: [14, 0.9, -8], isGrass: true },
        { type: 'TresBoxGeometry', args: [1.6, 0.2, 5.6], position: [8, 0.9, -14], isGrass: true },
        // 西北花坛
        { type: 'TresBoxGeometry', args: [6, 0.8, 2], position: [-14, 0.5, -8], isWall: true },
        { type: 'TresBoxGeometry', args: [2, 0.8, 6], position: [-8, 0.5, -14], isWall: true },
        { type: 'TresBoxGeometry', args: [5.6, 0.2, 1.6], position: [-14, 0.9, -8], isGrass: true },
        { type: 'TresBoxGeometry', args: [1.6, 0.2, 5.6], position: [-8, 0.9, -14], isGrass: true }
      ]
    },

    // ================== 中轴线 (南北) ==================
    {
      id: "B2", name: "图书馆", type: "公共", status: "正常", color: "#3b82f6",
      position: [0, 0, -45], scale: [30, 20, 30], 
      group: [
        // ================== 1. 核心退台结构主体 ==================
        ...generateBuildingWithWindows(30, 6, 30, 0, 3, 0),
        ...generateBuildingWithWindows(24, 8, 24, 0, 10, 0),
        ...generateBuildingWithWindows(16, 6, 16, 0, 17, 0),

        // ================== 2. 气派的大型迎宾阶梯与入口大堂 (朝南面广场) ==================
        // 宽大的层叠石阶
        { type: 'TresBoxGeometry', args: [16, 0.4, 4], position: [0, 0.2, 16], isGround: true },
        { type: 'TresBoxGeometry', args: [16, 0.8, 3], position: [0, 0.4, 15.5], isGround: true },
        { type: 'TresBoxGeometry', args: [16, 1.2, 2], position: [0, 0.6, 15], isGround: true },
        // 两层挑高的通透全玻璃大门
        { type: 'TresBoxGeometry', args: [12, 5, 1.5], position: [0, 2.5, 15], isGlass: true },
        // 大堂向外延伸的浮空金属挑檐雨棚
        { type: 'TresBoxGeometry', args: [16, 0.6, 6], position: [0, 5.3, 16], isWall: true },
        // 雨棚承重立柱
        { type: 'TresCylinderGeometry', args: [0.6, 0.6, 5.3, 16], position: [7, 2.65, 18], isWall: true },
        { type: 'TresCylinderGeometry', args: [0.6, 0.6, 5.3, 16], position: [-7, 2.65, 18], isWall: true },

        // ================== 3. 现代图书馆标志性：横向遮阳百叶栅格 (包裹第二层主体) ==================
        // 这种遮阳栅格赋予建筑极强的科技线条感，同时打破方块的沉闷
        { type: 'TresBoxGeometry', args: [24.8, 0.3, 24.8], position: [0, 7.5, 0], isWall: true },
        { type: 'TresBoxGeometry', args: [24.8, 0.3, 24.8], position: [0, 10, 0], isWall: true },
        { type: 'TresBoxGeometry', args: [24.8, 0.3, 24.8], position: [0, 12.5, 0], isWall: true },

        // ================== 4. 阶梯退台生态屋顶花园 (在一层屋顶铺设绿色空间) ==================
        { type: 'TresBoxGeometry', args: [29, 0.15, 2.5], position: [0, 6.1, 13.5], isGrass: true },
        { type: 'TresBoxGeometry', args: [29, 0.15, 2.5], position: [0, 6.1, -13.5], isGrass: true },
        { type: 'TresBoxGeometry', args: [2.5, 0.15, 24.5], position: [13.5, 6.1, 0], isGrass: true },
        { type: 'TresBoxGeometry', args: [2.5, 0.15, 24.5], position: [-13.5, 6.1, 0], isGrass: true },

        // ================== 5. 顶部全景采光穹顶 (玻璃金字塔天窗) ==================
        // 采光顶金属基座
        { type: 'TresBoxGeometry', args: [10, 0.5, 10], position: [0, 20.25, 0], isWall: true },
        // 玻璃金字塔主体 (利用底面积大、顶面积0的少边数圆柱体模拟四棱锥)
        { type: 'TresCylinderGeometry', args: [0, 5, 4, 4], position: [0, 22.5, 0], isGlass: true },
        // 玻璃天窗的十字钢结构骨架
        { type: 'TresBoxGeometry', args: [10.2, 4.2, 0.2], position: [0, 22.5, 0], isWall: true },
        { type: 'TresBoxGeometry', args: [0.2, 4.2, 10.2], position: [0, 22.5, 0], isWall: true }
      ]
    },
    {
      id: "B3", name: "行政办公楼", type: "办公", status: "正常", color: "#10b981",
      position: [0, 0, 45], scale: [35, 30, 15], 
      group: [
        // ================== 1. 核心基座与主塔 (完全保留原始生成) ==================
        ...generateBuildingWithWindows(35, 8, 15, 0, 4, 0),
        ...generateBuildingWithWindows(12, 28, 12, 0, 22, 0),

        // ================== 2. 垂直金属勒脚与装饰线条 (强化主塔的挺拔与威严感) ==================
        // 塔楼正面 (朝北) 的垂直线条
        { type: 'TresBoxGeometry', args: [0.6, 28, 1], position: [-3, 22, -6.5], isWall: true },
        { type: 'TresBoxGeometry', args: [0.6, 28, 1], position: [3, 22, -6.5], isWall: true },
        // 塔楼背面 (朝南) 的垂直线条
        { type: 'TresBoxGeometry', args: [0.6, 28, 1], position: [-3, 22, 6.5], isWall: true },
        { type: 'TresBoxGeometry', args: [0.6, 28, 1], position: [3, 22, 6.5], isWall: true },

        // ================== 3. 气派的政务大堂迎宾区 (朝向北侧中心广场) ==================
        // 宽阔的花岗岩/红毯阶梯
        { type: 'TresBoxGeometry', args: [12, 0.3, 3], position: [0, 0.15, -8.5], isGround: true },
        { type: 'TresBoxGeometry', args: [12, 0.6, 2], position: [0, 0.3, -8.0], isGround: true },
        // 挑高玻璃门厅
        { type: 'TresBoxGeometry', args: [10, 6, 2], position: [0, 3, -8.5], isGlass: true },
        // 巨大且威严的悬挑雨棚
        { type: 'TresBoxGeometry', args: [14, 0.8, 6], position: [0, 6.4, -9.5], isWall: true },
        // 两侧方柱 (使用方形柱体，比圆柱更显权力和硬朗)
        { type: 'TresBoxGeometry', args: [1.2, 6.4, 1.2], position: [6, 3.2, -11], isWall: true },
        { type: 'TresBoxGeometry', args: [1.2, 6.4, 1.2], position: [-6, 3.2, -11], isWall: true },

        // ================== 4. 楼顶直升机停机坪 (最高指挥中心的标志) ==================
        // 加宽的顶台基座
        { type: 'TresBoxGeometry', args: [13, 1, 13], position: [0, 36.5, 0], isWall: true }, 
        // 停机坪深色沥青底 (复用 isTrack 的深灰质感)
        { type: 'TresCylinderGeometry', args: [5.5, 5.5, 0.2, 32], position: [0, 37.1, 0], isTrack: true }, 
        // 停机坪边缘的发光引导灯圈 (利用 isWindow)
        { type: 'TresCylinderGeometry', args: [5.8, 5.8, 0.1, 32], position: [0, 37.05, 0], isWindow: true },

        // ================== 5. 广场前方旗杆阵列 ==================
        // 旗杆大理石基座
        { type: 'TresBoxGeometry', args: [5, 0.4, 1.2], position: [0, 0.2, -15], isWall: true }, 
        // 主旗杆 (最高)
        { type: 'TresCylinderGeometry', args: [0.08, 0.1, 7, 8], position: [0, 3.5, -15], isWall: true }, 
        // 左右副旗杆 (略矮)
        { type: 'TresCylinderGeometry', args: [0.06, 0.08, 6, 8], position: [-1.5, 3, -15], isWall: true }, 
        { type: 'TresCylinderGeometry', args: [0.06, 0.08, 6, 8], position: [1.5, 3, -15], isWall: true }
      ]
    },

    // ================== 东侧 (教学与会议区) ==================
    {
      id: "B1", name: "教学楼", type: "教学", status: "正常", color: "#0ea5e9",
      position: [45, 0, 0], scale: [20, 20, 40], 
      group: [
        // ================== 1. 核心 U 型主体 ==================
        ...generateBuildingWithWindows(12, 20, 40, 0, 10, 0),    
        ...generateBuildingWithWindows(15, 20, 10, -13.5, 10, 15), 
        ...generateBuildingWithWindows(15, 20, 10, -13.5, 10, -15),

        // ================== 2. 现代悬浮玻璃连廊 (连接南北两翼) ==================
        // 玻璃连廊主体 (位于4楼的高度)
        { type: 'TresBoxGeometry', args: [3, 4, 20], position: [-18, 14, 0], isGlass: true },
        // 连廊的顶部和底部金属框架
        { type: 'TresBoxGeometry', args: [3.5, 0.4, 20.5], position: [-18, 16.2, 0], isWall: true },
        { type: 'TresBoxGeometry', args: [3.5, 0.4, 20.5], position: [-18, 11.8, 0], isWall: true },

        // ================== 3. U型内庭院与阶梯式基座 ==================
        { type: 'TresBoxGeometry', args: [14, 0.4, 18], position: [-13, 0.2, 0], isGround: true },
        { type: 'TresBoxGeometry', args: [12, 0.4, 16], position: [-12, 0.6, 0], isGround: true },

        // ================== 4. 一楼通透的玻璃大堂与门头雨棚 ==================
        // 突出的全景玻璃大堂
        { type: 'TresBoxGeometry', args: [4, 6, 12], position: [-7, 3, 0], isGlass: true },
        // 门头大跨度雨棚
        { type: 'TresBoxGeometry', args: [6, 0.6, 14], position: [-10, 6, 0], isWall: true },
        // 雨棚支撑立柱
        { type: 'TresCylinderGeometry', args: [0.4, 0.4, 6, 16], position: [-12.5, 3, 6], isWall: true },
        { type: 'TresCylinderGeometry', args: [0.4, 0.4, 6, 16], position: [-12.5, 3, -6], isWall: true },

        // ================== 5. 楼顶集中式光伏发电阵列 (体现数字孪生智慧低碳) ==================
        // 主楼顶端机座
        { type: 'TresBoxGeometry', args: [5, 1, 32], position: [0, 21, 0], isWall: true },
        // 深色高亮光伏板 (用 isWindow 模拟深蓝色高反光发光材质)
        { type: 'TresBoxGeometry', args: [6, 0.2, 34], position: [0, 21.6, 0], isWindow: true },

        // ================== 6. 南北两翼端头装饰外骨骼框 ==================
        // 用包裹式的金属框包边两翼的端头，打破单调的白墙
        { type: 'TresBoxGeometry', args: [0.6, 21, 10.4], position: [-21.3, 10.5, 15], isWall: true },
        { type: 'TresBoxGeometry', args: [0.6, 21, 10.4], position: [-21.3, 10.5, -15], isWall: true },
        
        // ================== 7. 主楼中央垂直电梯交通核 ==================
        { type: 'TresBoxGeometry', args: [1.5, 23, 6], position: [-6, 11.5, 0], isWall: true }
      ]
    },
    {
      id: "B8", name: "会议交流中心", type: "公共", status: "故障", color: "#ef4444",
      position: [45, 0, 45], scale: [25, 15, 25], 
      group: [
        // ================== 1. 圆形基座阶梯 (增加庄重感) ==================
        { type: 'TresCylinderGeometry', args: [21, 21, 0.4, 64], position: [0, 0.2, 0], isGround: true },
        { type: 'TresCylinderGeometry', args: [20, 20, 0.4, 64], position: [0, 0.6, 0], isGround: true },

        // ================== 2. 底层通透玻璃大堂 ==================
        { type: 'TresCylinderGeometry', args: [14, 14, 5, 32], position: [0, 3.3, 0], isGlass: true },

        // ================== 3. 环形外围承重立柱 (8根，支撑二楼的悬挑) ==================
        { type: 'TresCylinderGeometry', args: [0.6, 0.6, 5, 16], position: [16, 3.3, 0], isWall: true },
        { type: 'TresCylinderGeometry', args: [0.6, 0.6, 5, 16], position: [-16, 3.3, 0], isWall: true },
        { type: 'TresCylinderGeometry', args: [0.6, 0.6, 5, 16], position: [0, 3.3, 16], isWall: true },
        { type: 'TresCylinderGeometry', args: [0.6, 0.6, 5, 16], position: [0, 3.3, -16], isWall: true },
        { type: 'TresCylinderGeometry', args: [0.6, 0.6, 5, 16], position: [11.3, 3.3, 11.3], isWall: true },
        { type: 'TresCylinderGeometry', args: [0.6, 0.6, 5, 16], position: [-11.3, 3.3, 11.3], isWall: true },
        { type: 'TresCylinderGeometry', args: [0.6, 0.6, 5, 16], position: [11.3, 3.3, -11.3], isWall: true },
        { type: 'TresCylinderGeometry', args: [0.6, 0.6, 5, 16], position: [-11.3, 3.3, -11.3], isWall: true },

        // ================== 4. 二层主体建筑 (倒圆锥悬挑设计，极具现代张力) ==================
        { type: 'TresCylinderGeometry', args: [18, 14, 6, 64], position: [0, 8.8, 0], isWall: true },
        
        // ================== 5. 二层环形条带窗 (嵌套在倒圆锥外侧) ==================
        // 使用 isWindow 材质使其具有高亮反光效果
        { type: 'TresCylinderGeometry', args: [18.2, 16.2, 1.5, 64], position: [0, 9.5, 0], isWindow: true },

        // ================== 6. 顶层环形屋檐 ==================
        { type: 'TresCylinderGeometry', args: [18.2, 18, 1, 64], position: [0, 12.3, 0], isWall: true },

        // ================== 7. 核心会场穹顶 ==================
        { type: 'TresSphereGeometry', args: [10, 32, 16], position: [0, 12.5, 0], isWindow: true },
        // 穹顶底部加固环
        { type: 'TresCylinderGeometry', args: [10.5, 10.5, 0.6, 64], position: [0, 12.5, 0], isWall: true },

        // ================== 8. 迎宾大堂入口 (向外延伸的玻璃门头和宽大雨棚) ==================
        { type: 'TresBoxGeometry', args: [12, 4, 8], position: [0, 2.6, 15], isGlass: true },
        { type: 'TresBoxGeometry', args: [14, 0.6, 10], position: [0, 4.9, 16], isWall: true }
      ]
    },
    {
      id: "B6", name: "学生宿舍", type: "生活", status: "正常", color: "#10b981",
      position: [45, 0, -45], scale: [30, 25, 20], 
      group: [
        // ================== 1. 宿舍双子塔主体 ==================
        ...generateBuildingWithWindows(10, 25, 20, -10, 12.5, 0),
        ...generateBuildingWithWindows(10, 25, 20, 10, 12.5, 0),

        // ================== 2. 底层共享生活广场基座 ==================
        { type: 'TresBoxGeometry', args: [26, 0.4, 24], position: [0, 0.2, 0], isGround: true },

        // ================== 3. 空中全息玻璃连廊 (带金属装甲框架) ==================
        // 上层连廊主体 (高亮深色玻璃)
        { type: 'TresBoxGeometry', args: [10, 4, 6], position: [0, 18, 0], isGlass: true },
        // 上层连廊上下金属边框
        { type: 'TresBoxGeometry', args: [10.2, 0.4, 6.4], position: [0, 20.2, 0], isWall: true },
        { type: 'TresBoxGeometry', args: [10.2, 0.4, 6.4], position: [0, 15.8, 0], isWall: true },

        // 下层连廊主体 (高亮深色玻璃)
        { type: 'TresBoxGeometry', args: [10, 4, 6], position: [0, 6, 0], isGlass: true },
        // 下层连廊上下金属边框
        { type: 'TresBoxGeometry', args: [10.2, 0.4, 6.4], position: [0, 8.2, 0], isWall: true },
        { type: 'TresBoxGeometry', args: [10.2, 0.4, 6.4], position: [0, 3.8, 0], isWall: true },

        // ================== 4. 楼顶生活设施 (科幻风温控/储水塔) ==================
        // 左塔顶部设施
        { type: 'TresCylinderGeometry', args: [2, 2, 3, 16], position: [-10, 26.5, -4], isWall: true },
        { type: 'TresCylinderGeometry', args: [2.2, 2.2, 0.2, 16], position: [-10, 27.5, -4], isWindow: true }, // 霓虹发光环
        // 右塔顶部设施
        { type: 'TresCylinderGeometry', args: [2, 2, 3, 16], position: [10, 26.5, -4], isWall: true },
        { type: 'TresCylinderGeometry', args: [2.2, 2.2, 0.2, 16], position: [10, 27.5, -4], isWindow: true },

        // ================== 5. 🌲 核心细节：专属庭院全息晶体树阵列 ==================
        
        // ① 中心前庭院全息树
        { type: 'TresCylinderGeometry', args: [0.15, 0.25, 1.5, 6], position: [0, 0.95, 8], isWall: true }, // 树干
        { type: 'TresCylinderGeometry', args: [1.2, 1.2, 0.05, 16], position: [0, 0.45, 8], isWindow: true }, // 底部全息光环
        { type: 'TresSphereGeometry', args: [1.8, 5, 4], position: [0, 3.4, 8], isGlass: true }, // 玻璃外壳
        { type: 'TresSphereGeometry', args: [1.2, 4, 3], position: [0, 3.2, 8], isGlass: true }, // 错位晶体内壳
        { type: 'TresSphereGeometry', args: [0.5, 8, 8], position: [0, 3.4, 8], isWindow: true }, // 核心发光数据核

        // ② 中心后庭院全息树
        { type: 'TresCylinderGeometry', args: [0.15, 0.25, 1.5, 6], position: [0, 0.95, -8], isWall: true }, 
        { type: 'TresCylinderGeometry', args: [1.2, 1.2, 0.05, 16], position: [0, 0.45, -8], isWindow: true }, 
        { type: 'TresSphereGeometry', args: [1.8, 5, 4], position: [0, 3.4, -8], isGlass: true }, 
        { type: 'TresSphereGeometry', args: [1.2, 4, 3], position: [0, 3.2, -8], isGlass: true }, 
        { type: 'TresSphereGeometry', args: [0.5, 8, 8], position: [0, 3.4, -8], isWindow: true },
        
        // ③ 左塔入口侧边全息树
        { type: 'TresCylinderGeometry', args: [0.15, 0.25, 1.5, 6], position: [-13, 0.95, 8], isWall: true }, 
        { type: 'TresCylinderGeometry', args: [1.2, 1.2, 0.05, 16], position: [-13, 0.45, 8], isWindow: true }, 
        { type: 'TresSphereGeometry', args: [1.8, 5, 4], position: [-13, 3.4, 8], isGlass: true }, 
        { type: 'TresSphereGeometry', args: [1.2, 4, 3], position: [-13, 3.2, 8], isGlass: true }, 
        { type: 'TresSphereGeometry', args: [0.5, 8, 8], position: [-13, 3.4, 8], isWindow: true },

        // ④ 右塔入口侧边全息树
        { type: 'TresCylinderGeometry', args: [0.15, 0.25, 1.5, 6], position: [13, 0.95, 8], isWall: true }, 
        { type: 'TresCylinderGeometry', args: [1.2, 1.2, 0.05, 16], position: [13, 0.45, 8], isWindow: true }, 
        { type: 'TresSphereGeometry', args: [1.8, 5, 4], position: [13, 3.4, 8], isGlass: true }, 
        { type: 'TresSphereGeometry', args: [1.2, 4, 3], position: [13, 3.2, 8], isGlass: true }, 
        { type: 'TresSphereGeometry', args: [0.5, 8, 8], position: [13, 3.4, 8], isWindow: true }
      ]
    },

    // ================== 西侧 (科研与生活区) ==================
    {
      id: "B4", name: "科研实验楼", type: "实验", status: "警告", color: "#f59e0b",
      position: [-45, 0, 0], scale: [25, 25, 25], 
      group: [
        // ================== 1. 核心主体 (带独立小方块窗户) ==================
        ...generateBuildingWithWindows(25, 15, 25, 0, 7.5, 0),

        // ================== 2. 实验楼底部加固基座 (增加重工业感) ==================
        { type: 'TresBoxGeometry', args: [28, 1.5, 28], position: [0, 0.75, 0], isGround: true },

        // ================== 3. 外骨骼：四角承重塔柱 ==================
        { type: 'TresBoxGeometry', args: [3.5, 23, 3.5], position: [12.5, 11.5, 12.5], isWall: true },
        { type: 'TresBoxGeometry', args: [3.5, 23, 3.5], position: [-12.5, 11.5, 12.5], isWall: true },
        { type: 'TresBoxGeometry', args: [3.5, 23, 3.5], position: [12.5, 11.5, -12.5], isWall: true },
        { type: 'TresBoxGeometry', args: [3.5, 23, 3.5], position: [-12.5, 11.5, -12.5], isWall: true },

        // ================== 4. 外骨骼：顶部环形连廊 (连接四柱) ==================
        { type: 'TresBoxGeometry', args: [28.5, 1.5, 3.5], position: [0, 22.25, 12.5], isWall: true },
        { type: 'TresBoxGeometry', args: [28.5, 1.5, 3.5], position: [0, 22.25, -12.5], isWall: true },
        { type: 'TresBoxGeometry', args: [3.5, 1.5, 21.5], position: [12.5, 22.25, 0], isWall: true },
        { type: 'TresBoxGeometry', args: [3.5, 1.5, 21.5], position: [-12.5, 22.25, 0], isWall: true },

        // ================== 5. 顶层核心：天文/微波观测穹顶 ==================
        // 穹顶金属轨道底座
        { type: 'TresCylinderGeometry', args: [10.5, 10.5, 2, 32], position: [0, 16, 0], isWall: true },
        // 深邃反光玻璃穹顶主体 (改用 isGlass 拥有深色镜面质感)
        { type: 'TresSphereGeometry', args: [10, 32, 16], position: [0, 16, 0], isGlass: true },
        
        // ================== 6. 穹顶顶端信号接收天线 ==================
        { type: 'TresCylinderGeometry', args: [0.2, 0.4, 6, 8], position: [0, 28, 0], isWall: true },
        { type: 'TresSphereGeometry', args: [0.6, 16, 16], position: [0, 31, 0], isWindow: true }, // 发光信号灯

        // ================== 7. 楼顶通风与冷却排气管道 (四角阵列) ==================
        { type: 'TresCylinderGeometry', args: [1.5, 1.5, 4, 16], position: [9, 17, 9], isWall: true },
        { type: 'TresCylinderGeometry', args: [1.5, 1.5, 4, 16], position: [-9, 17, 9], isWall: true },
        { type: 'TresCylinderGeometry', args: [1.5, 1.5, 4, 16], position: [9, 17, -9], isWall: true },
        { type: 'TresCylinderGeometry', args: [1.5, 1.5, 4, 16], position: [-9, 17, -9], isWall: true },
        
        // ================== 8. 实验室正门突出的玻璃门头与金属雨棚 ==================
        { type: 'TresBoxGeometry', args: [8, 3, 4], position: [0, 1.5, 13.5], isGlass: true },
        { type: 'TresBoxGeometry', args: [8.5, 0.5, 4.5], position: [0, 3.25, 13.5], isWall: true }
      ]
    },
    {
      id: "B5", name: "食堂", type: "生活", status: "正常", color: "#10b981",
      position: [-45, 0, -45], scale: [25, 12, 25], 
      group: [
        // ================== 1. 核心主体 (带独立小方块窗户) ==================
        ...generateBuildingWithWindows(25, 12, 25, 0, 6, 0),

        // ================== 2. 一楼全景玻璃餐厅 (向外凸出，朝向校园中心) ==================
        // 玻璃幕墙主体
        { type: 'TresBoxGeometry', args: [20, 5, 6], position: [0, 2.5, 14.5], isGlass: true },
        // 玻璃餐厅的金属雨棚
        { type: 'TresBoxGeometry', args: [21, 0.6, 6.5], position: [0, 5.3, 14.75], isWall: true },

        // ================== 3. 后厨排烟排气系统 (屋顶大型工业机组) ==================
        // 巨型排烟囱
        { type: 'TresCylinderGeometry', args: [2, 2, 8, 16], position: [-6, 16, -6], isWall: true },
        { type: 'TresCylinderGeometry', args: [2, 2, 8, 16], position: [6, 16, -6], isWall: true },
        // 烟囱顶部的防雨帽 (扩大一圈的圆盘)
        { type: 'TresCylinderGeometry', args: [2.5, 2.5, 0.4, 16], position: [-6, 20.2, -6], isWall: true },
        { type: 'TresCylinderGeometry', args: [2.5, 2.5, 0.4, 16], position: [6, 20.2, -6], isWall: true },

        // ================== 4. 屋顶中央空调与冷凝机组 ==================
        // 大型方形机箱
        { type: 'TresBoxGeometry', args: [8, 3, 10], position: [0, 14, 4], isWall: true },
        // 机箱顶部的散热风扇开口 (利用 isGlass 的深色反光模拟)
        { type: 'TresCylinderGeometry', args: [1.8, 1.8, 0.2, 16], position: [0, 15.6, 1.5], isGlass: true },
        { type: 'TresCylinderGeometry', args: [1.8, 1.8, 0.2, 16], position: [0, 15.6, 6.5], isGlass: true },

        // ================== 5. 食材装卸货月台 (建筑背面) ==================
        // 卸货高台
        { type: 'TresBoxGeometry', args: [12, 1.5, 4], position: [0, 0.75, -14.5], isGround: true },
        // 卸货区防雨棚
        { type: 'TresBoxGeometry', args: [12, 0.4, 4.5], position: [0, 4.5, -14.75], isWall: true },
        // 支撑雨棚的侧边柱子
        { type: 'TresBoxGeometry', args: [0.4, 3, 0.4], position: [5.8, 3, -16.5], isWall: true },
        { type: 'TresBoxGeometry', args: [0.4, 3, 0.4], position: [-5.8, 3, -16.5], isWall: true }
      ]
    },

    // ================== 大西侧 (专属运动区) ==================
    // ================== 大西侧 (专属运动区) ==================
    {
      id: "B10", name: "主篮球场", type: "运动", status: "正常", color: "#64748b",
      position: [-80, 0, -45], scale: [20, 1, 30], 
      group: [
        // ================== 1. 科幻悬浮球场基座与地面 ==================
        { type: 'TresBoxGeometry', args: [21, 0.2, 31], position: [0, 0.1, 0], isGround: true }, // 外圈深色基座
        { type: 'TresBoxGeometry', args: [20, 0.25, 30], position: [0, 0.15, 0], isTrack: true }, // 内圈深黑胶场地
        
        // ================== 2. 发光场地边界线与中圈 (全息霓虹感) ==================
        { type: 'TresBoxGeometry', args: [19, 0.26, 0.2], position: [0, 0.16, 14], isWindow: true }, // 北底线
        { type: 'TresBoxGeometry', args: [19, 0.26, 0.2], position: [0, 0.16, -14], isWindow: true }, // 南底线
        { type: 'TresBoxGeometry', args: [0.2, 0.26, 28], position: [9.4, 0.16, 0], isWindow: true }, // 东边线
        { type: 'TresBoxGeometry', args: [0.2, 0.26, 28], position: [-9.4, 0.16, 0], isWindow: true }, // 西边线
        { type: 'TresBoxGeometry', args: [19, 0.26, 0.2], position: [0, 0.16, 0], isWindow: true }, // 中线
        { type: 'TresCylinderGeometry', args: [3, 3, 0.26, 32], position: [0, 0.16, 0], isWindow: true }, // 全息发光中圈

        // ================== 3. 次世代篮球架 (悬浮玻璃篮板 + 机械臂) ==================
        // 东侧篮架
        { type: 'TresBoxGeometry', args: [0.6, 4, 0.6], position: [8.5, 2, 0], isWall: true }, // 粗壮机械立柱
        { type: 'TresBoxGeometry', args: [1.2, 0.4, 0.4], position: [8.5, 4, 0], isWall: true }, // 向内延伸的机械臂
        { type: 'TresBoxGeometry', args: [0.2, 2.5, 4], position: [7.8, 4.5, 0], isGlass: true }, // 高反光玻璃篮板
        { type: 'TresBoxGeometry', args: [0.3, 0.1, 0.8], position: [7.6, 3.8, 0], isWindow: true }, // 发光篮筐圈(极简方块代表)
        // 西侧篮架
        { type: 'TresBoxGeometry', args: [0.6, 4, 0.6], position: [-8.5, 2, 0], isWall: true }, 
        { type: 'TresBoxGeometry', args: [1.2, 0.4, 0.4], position: [-8.5, 4, 0], isWall: true }, 
        { type: 'TresBoxGeometry', args: [0.2, 2.5, 4], position: [-7.8, 4.5, 0], isGlass: true }, 
        { type: 'TresBoxGeometry', args: [0.3, 0.1, 0.8], position: [-7.6, 3.8, 0], isWindow: true },

        // ================== 4. 球场四角高能探照灯塔 ==================
        // 东北角
        { type: 'TresCylinderGeometry', args: [0.2, 0.3, 10, 8], position: [9.5, 5, 14.5], isWall: true },
        { type: 'TresBoxGeometry', args: [1.5, 0.6, 0.8], position: [9, 9.8, 14], isWindow: true }, // 发光灯头朝内侧
        // 西北角
        { type: 'TresCylinderGeometry', args: [0.2, 0.3, 10, 8], position: [-9.5, 5, 14.5], isWall: true },
        { type: 'TresBoxGeometry', args: [1.5, 0.6, 0.8], position: [-9, 9.8, 14], isWindow: true },
        // 东南角
        { type: 'TresCylinderGeometry', args: [0.2, 0.3, 10, 8], position: [9.5, 5, -14.5], isWall: true },
        { type: 'TresBoxGeometry', args: [1.5, 0.6, 0.8], position: [9, 9.8, -14], isWindow: true },
        // 西南角
        { type: 'TresCylinderGeometry', args: [0.2, 0.3, 10, 8], position: [-9.5, 5, -14.5], isWall: true },
        { type: 'TresBoxGeometry', args: [1.5, 0.6, 0.8], position: [-9, 9.8, -14], isWindow: true },

        // ================== 5. 科幻护盾围栏 (金属框架 + 全息防爆玻璃) ==================
        // 东/西向长围栏顶部扶手边框
        { type: 'TresBoxGeometry', args: [0.4, 0.4, 30], position: [10, 3, 0], isWall: true }, 
        { type: 'TresBoxGeometry', args: [0.4, 0.4, 30], position: [-10, 3, 0], isWall: true },
        // 东/西侧大面积防爆玻璃面板
        { type: 'TresBoxGeometry', args: [0.1, 2.5, 29.5], position: [10, 1.5, 0], isGlass: true }, 
        { type: 'TresBoxGeometry', args: [0.1, 2.5, 29.5], position: [-10, 1.5, 0], isGlass: true },
        // 南/北向短围栏顶部扶手边框
        { type: 'TresBoxGeometry', args: [20, 0.4, 0.4], position: [0, 3, 15], isWall: true },
        { type: 'TresBoxGeometry', args: [20, 0.4, 0.4], position: [0, 3, -15], isWall: true },
        // 南/北侧大面积防爆玻璃面板
        { type: 'TresBoxGeometry', args: [19.5, 2.5, 0.1], position: [0, 1.5, 15], isGlass: true },
        { type: 'TresBoxGeometry', args: [19.5, 2.5, 0.1], position: [0, 1.5, -15], isGlass: true },
        
        // ================== 6. 场边科技风休息棚 (南边外延) ==================
        { type: 'TresBoxGeometry', args: [8, 0.2, 3], position: [0, 2.5, -16], isWall: true }, // 顶棚
        { type: 'TresBoxGeometry', args: [0.2, 2.5, 0.2], position: [3.8, 1.25, -16.5], isWall: true }, // 顶棚后置支撑
        { type: 'TresBoxGeometry', args: [0.2, 2.5, 0.2], position: [-3.8, 1.25, -16.5], isWall: true },
        { type: 'TresBoxGeometry', args: [7, 0.4, 1], position: [0, 0.6, -16], isGlass: true } // 玻璃晶体座椅
      ]
    },
    {
      id: "B12", name: "副篮球场", type: "运动", status: "正常", color: "#64748b",
      position: [-80, 0, 45], scale: [20, 1, 30], 
      group: [
        // ================== 1. 场地基座与内场 ==================
        { type: 'TresBoxGeometry', args: [21, 0.2, 31], position: [0, 0.1, 0], isGround: true }, 
        { type: 'TresBoxGeometry', args: [20, 0.25, 30], position: [0, 0.15, 0], isTrack: true }, 
        
        // ================== 2. 发光场地边界线 (全息效果) ==================
        { type: 'TresBoxGeometry', args: [19, 0.26, 0.2], position: [0, 0.16, 14], isWindow: true }, 
        { type: 'TresBoxGeometry', args: [19, 0.26, 0.2], position: [0, 0.16, -14], isWindow: true },
        { type: 'TresBoxGeometry', args: [0.2, 0.26, 28], position: [9.4, 0.16, 0], isWindow: true }, 
        { type: 'TresBoxGeometry', args: [0.2, 0.26, 28], position: [-9.4, 0.16, 0], isWindow: true },
        { type: 'TresBoxGeometry', args: [19, 0.26, 0.2], position: [0, 0.16, 0], isWindow: true }, // 中线
        { type: 'TresCylinderGeometry', args: [3, 3, 0.26, 32], position: [0, 0.16, 0], isWindow: true }, // 中圈

        // ================== 3. 机械悬挑篮架与玻璃篮板 ==================
        // 东侧篮架
        { type: 'TresBoxGeometry', args: [0.6, 4, 0.6], position: [8.5, 2, 0], isWall: true }, 
        { type: 'TresBoxGeometry', args: [1.2, 0.4, 0.4], position: [8.5, 4, 0], isWall: true }, 
        { type: 'TresBoxGeometry', args: [0.2, 2.5, 4], position: [7.8, 4.5, 0], isGlass: true }, 
        { type: 'TresBoxGeometry', args: [0.3, 0.1, 0.8], position: [7.6, 3.8, 0], isWindow: true },
        // 西侧篮架
        { type: 'TresBoxGeometry', args: [0.6, 4, 0.6], position: [-8.5, 2, 0], isWall: true }, 
        { type: 'TresBoxGeometry', args: [1.2, 0.4, 0.4], position: [-8.5, 4, 0], isWall: true }, 
        { type: 'TresBoxGeometry', args: [0.2, 2.5, 4], position: [-7.8, 4.5, 0], isGlass: true }, 
        { type: 'TresBoxGeometry', args: [0.3, 0.1, 0.8], position: [-7.6, 3.8, 0], isWindow: true },

        // ================== 4. 四角高能探照灯阵列 ==================
        { type: 'TresCylinderGeometry', args: [0.2, 0.3, 10, 8], position: [9.5, 5, 14.5], isWall: true },
        { type: 'TresBoxGeometry', args: [1.5, 0.6, 0.8], position: [9, 9.8, 14], isWindow: true },
        { type: 'TresCylinderGeometry', args: [0.2, 0.3, 10, 8], position: [-9.5, 5, 14.5], isWall: true },
        { type: 'TresBoxGeometry', args: [1.5, 0.6, 0.8], position: [-9, 9.8, 14], isWindow: true },
        { type: 'TresCylinderGeometry', args: [0.2, 0.3, 10, 8], position: [9.5, 5, -14.5], isWall: true },
        { type: 'TresBoxGeometry', args: [1.5, 0.6, 0.8], position: [9, 9.8, -14], isWindow: true },
        { type: 'TresCylinderGeometry', args: [0.2, 0.3, 10, 8], position: [-9.5, 5, -14.5], isWall: true },
        { type: 'TresBoxGeometry', args: [1.5, 0.6, 0.8], position: [-9, 9.8, -14], isWindow: true },

        // ================== 5. 全息能量护盾 (防爆玻璃面板) ==================
        { type: 'TresBoxGeometry', args: [0.4, 0.4, 30], position: [10, 3, 0], isWall: true }, 
        { type: 'TresBoxGeometry', args: [0.4, 0.4, 30], position: [-10, 3, 0], isWall: true },
        { type: 'TresBoxGeometry', args: [0.1, 2.5, 29.5], position: [10, 1.5, 0], isGlass: true }, 
        { type: 'TresBoxGeometry', args: [0.1, 2.5, 29.5], position: [-10, 1.5, 0], isGlass: true },
        { type: 'TresBoxGeometry', args: [20, 0.4, 0.4], position: [0, 3, 15], isWall: true },
        { type: 'TresBoxGeometry', args: [20, 0.4, 0.4], position: [0, 3, -15], isWall: true },
        { type: 'TresBoxGeometry', args: [19.5, 2.5, 0.1], position: [0, 1.5, 15], isGlass: true },
        { type: 'TresBoxGeometry', args: [19.5, 2.5, 0.1], position: [0, 1.5, -15], isGlass: true }
      ]
    },
    {
      id: "B11", name: "环形田径场", type: "运动", status: "正常", color: "#64748b",
      position: [-125, 0, 0], scale: [40, 1, 60], 
      group: [
        // ================== 1. 跑道系统 (深黑胶+发光刻度线) ==================
        { type: 'TresBoxGeometry', args: [36, 0.1, 40], position: [0, 0.05, 0], isTrack: true },
        { type: 'TresCylinderGeometry', args: [18, 18, 0.1, 32], position: [0, 0.05, 20], isTrack: true },
        { type: 'TresCylinderGeometry', args: [18, 18, 0.1, 32], position: [0, 0.05, -20], isTrack: true },
        // 发光跑道道线 (利用 isWindow 材质的自发光)
        { type: 'TresBoxGeometry', args: [0.2, 0.12, 40], position: [8, 0.06, 0], isWindow: true },
        { type: 'TresBoxGeometry', args: [0.2, 0.12, 40], position: [-8, 0.06, 0], isWindow: true },

        // ================== 2. 足球场草坪与全息边线 ==================
        { type: 'TresBoxGeometry', args: [24, 0.12, 40], position: [0, 0.06, 0], isGrass: true },
        { type: 'TresCylinderGeometry', args: [12, 12, 0.12, 32], position: [0, 0.06, 20], isGrass: true },
        { type: 'TresCylinderGeometry', args: [12, 12, 0.12, 32], position: [0, 0.06, -20], isGrass: true },
        // 发光边线
        { type: 'TresBoxGeometry', args: [24, 0.13, 0.2], position: [0, 0.065, 20], isWindow: true },
        { type: 'TresBoxGeometry', args: [24, 0.13, 0.2], position: [0, 0.065, -20], isWindow: true },

        // ================== 3. 足球门框 (加固) ==================
        { type: 'TresBoxGeometry', args: [4, 1.2, 0.3], position: [0, 0.6, 28], isWall: true },
        { type: 'TresBoxGeometry', args: [0.2, 1.2, 0.3], position: [2, 0.6, 28], isWall: true },
        { type: 'TresBoxGeometry', args: [0.2, 1.2, 0.3], position: [-2, 0.6, 28], isWall: true },

        // ================== 4. 西侧阶梯看台 (工业骨架) ==================
        { type: 'TresBoxGeometry', args: [3, 0.6, 40], position: [-19.5, 0.3, 0], isWall: true },
        { type: 'TresBoxGeometry', args: [3, 1.2, 40], position: [-21.5, 0.6, 0], isWall: true },
        { type: 'TresBoxGeometry', args: [3, 1.8, 40], position: [-23.5, 0.9, 0], isWall: true },
        // 阶梯看台独立登场通道
        { type: 'TresBoxGeometry', args: [2, 0.9, 2], position: [-20.5, 0.45, 12], isWall: true },
        { type: 'TresBoxGeometry', args: [2, 0.9, 2], position: [-20.5, 0.45, -12], isWall: true },
        // 玻璃遮阳顶棚
        { type: 'TresBoxGeometry', args: [8, 0.2, 40], position: [-21.5, 3.5, 0], isGlass: true },

        // ================== 5. 探照灯塔 (带散热器阵列) ==================
        // 塔柱
        { type: 'TresCylinderGeometry', args: [0.3, 0.4, 10, 8], position: [-18, 5, 32], isWall: true },
        { type: 'TresCylinderGeometry', args: [0.3, 0.4, 10, 8], position: [-18, 5, -32], isWall: true },
        { type: 'TresCylinderGeometry', args: [0.3, 0.4, 10, 8], position: [18, 5, 32], isWall: true },
        { type: 'TresCylinderGeometry', args: [0.3, 0.4, 10, 8], position: [18, 5, -32], isWall: true },
        // 灯头组件 (带有散热纹理的灯箱)
        { type: 'TresBoxGeometry', args: [1.8, 1, 1], position: [-17, 9.8, 31.5], isWindow: true },
        { type: 'TresBoxGeometry', args: [1.8, 1, 1], position: [-17, 9.8, -31.5], isWindow: true },
        { type: 'TresBoxGeometry', args: [1.8, 1, 1], position: [17, 9.8, 31.5], isWindow: true },
        { type: 'TresBoxGeometry', args: [1.8, 1, 1], position: [17, 9.8, -31.5], isWindow: true },

        // ================== 6. 跑道起跑器点位 ==================
        { type: 'TresBoxGeometry', args: [0.6, 0.2, 0.4], position: [0, 0.1, 15], isWindow: true },
        { type: 'TresBoxGeometry', args: [0.6, 0.2, 0.4], position: [2, 0.1, 15], isWindow: true },
        { type: 'TresBoxGeometry', args: [0.6, 0.2, 0.4], position: [-2, 0.1, 15], isWindow: true },

        // ================== 7. 场地外围护盾 ==================
        { type: 'TresBoxGeometry', args: [0.2, 2.5, 80], position: [-26, 1.25, 0], isGlass: true }, // 透明护盾围墙
        { type: 'TresBoxGeometry', args: [0.2, 2.5, 80], position: [22, 1.25, 0], isGlass: true }, 
        { type: 'TresBoxGeometry', args: [48.2, 2.5, 0.2], position: [-2, 1.25, 40], isWall: true }, 
        { type: 'TresBoxGeometry', args: [48.2, 2.5, 0.2], position: [-2, 1.25, -40], isWall: true } 
      ]
    },

    // ================== 🌟 新增：生态人工湖 ==================
    // ================== 🌟 新增：数字生态水体与监测栈道 ==================
    {
      id: "L2", name: "生态数据人工湖", type: "景观", status: "正常", color: "#64748b",
      position: [75, 0, -20], scale: [1, 1, 1], // 位于校园东部
      group: [
        // ================== 1. 湖底护岸与驳岸 (科技感硬边缘) ==================
        { type: 'TresCylinderGeometry', args: [20.5, 20.5, 0.15, 64], position: [0, 0.05, 0], isGround: true },
        { type: 'TresCylinderGeometry', args: [14.5, 14.5, 0.15, 64], position: [-12, 0.05, 12], isGround: true },
        // 发光驳岸线 (环绕湖边的霓虹光带，用薄薄的一层套在边缘)
        { type: 'TresCylinderGeometry', args: [20.2, 20, 0.16, 64], position: [0, 0.08, 0], isWindow: true },
        
        // ================== 2. 深邃发光水体 (全息液态水面) ==================
        { type: 'TresCylinderGeometry', args: [20, 20, 0.1, 64], position: [0, 0.1, 0], isGlass: true },
        { type: 'TresCylinderGeometry', args: [14, 14, 0.1, 64], position: [-12, 0.1, 12], isGlass: true },

        // ================== 3. 跨湖全息景观栈桥 ==================
        // 主栈道板
        { type: 'TresBoxGeometry', args: [3, 0.2, 20], position: [0, 0.4, 10], isWall: true },
        // 栈道两侧的发光科技扶手
        { type: 'TresBoxGeometry', args: [0.2, 0.4, 20], position: [1.4, 0.6, 10], isWindow: true },
        { type: 'TresBoxGeometry', args: [0.2, 0.4, 20], position: [-1.4, 0.6, 10], isWindow: true },

        // ================== 4. 湖心生态数据监测塔 (八边形科技塔) ==================
        // 湖心悬浮金属底座
        { type: 'TresCylinderGeometry', args: [5, 4, 0.6, 8], position: [0, 0.4, 0], isWall: true },
        // 核心水质数据机房 (全玻璃塔)
        { type: 'TresCylinderGeometry', args: [2.5, 2.5, 3.5, 8], position: [0, 2.4, 0], isGlass: true },
        // 外部承重外骨骼支柱
        { type: 'TresBoxGeometry', args: [0.4, 4.5, 0.4], position: [3.5, 2.5, 0], isWall: true },
        { type: 'TresBoxGeometry', args: [0.4, 4.5, 0.4], position: [-3.5, 2.5, 0], isWall: true },
        { type: 'TresBoxGeometry', args: [0.4, 4.5, 0.4], position: [0, 2.5, 3.5], isWall: true },
        { type: 'TresBoxGeometry', args: [0.4, 4.5, 0.4], position: [0, 2.5, -3.5], isWall: true },
        // 科技亭金属悬挑屋顶
        { type: 'TresCylinderGeometry', args: [6, 6, 0.4, 8], position: [0, 4.5, 0], isWall: true },
        // 屋顶全息投影数据环
        { type: 'TresCylinderGeometry', args: [2.5, 2.5, 0.2, 16], position: [0, 4.8, 0], isWindow: true },

        // ================== 5. 水面漂浮的数据采集浮标 ==================
        { type: 'TresSphereGeometry', args: [0.5, 16, 16], position: [12, 0.2, -8], isWindow: true },
        { type: 'TresSphereGeometry', args: [0.5, 16, 16], position: [-10, 0.2, -6], isWindow: true },
        { type: 'TresSphereGeometry', args: [0.5, 16, 16], position: [-18, 0.2, 18], isWindow: true },
      ]
    },

    // ================== 🌟 自动生成的路网与绿化层 ==================
    {
      id: "L1", name: "校园路网与绿化", type: "景观", status: "正常", color: "#64748b",
      position: [0, 0, 0], scale: [1, 1, 1],
      group: generateRoadsAndTrees()
    }
  ]
}