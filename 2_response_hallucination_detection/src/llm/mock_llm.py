"""Mock LLM 响应 — 预设的模拟检测结果

基于 ground_truth 调整，部分 case 模拟真实 LLM 可能出现的判断偏差（如 h20 置信度较低）。
"""

MOCK_RESPONSES = {
    "h01": {
        "is_hallucination": True,
        "hallucination_type": "政策编造",
        "confidence": 0.95,
        "evidence": "回复说'30天无理由退货且运费由商家承担'，但知识库是'7天无理由，非质量问题退货运费买家承担'。退货天数和运费政策均与知识库矛盾。",
        "severity": "high",
        "claims_analysis": [
            {"claim": "全品类支持30天无理由退货", "verdict": "contradicted", "explanation": "知识库为7天无理由"},
            {"claim": "运费由商家承担", "verdict": "contradicted", "explanation": "非质量问题退货运费由买家承担"}
        ]
    },
    "h02": {
        "is_hallucination": True,
        "hallucination_type": "参数编造",
        "confidence": 0.95,
        "evidence": "回复说'蓝牙5.3，支持多设备连接，延迟40ms'，但知识库是'蓝牙5.0，单设备连接，延迟约80ms'。三项参数全部编造。",
        "severity": "high",
        "claims_analysis": [
            {"claim": "蓝牙5.3版本", "verdict": "contradicted", "explanation": "知识库标注为蓝牙5.0"},
            {"claim": "支持多设备同时连接", "verdict": "contradicted", "explanation": "知识库说支持单设备连接"},
            {"claim": "延迟低至40ms", "verdict": "contradicted", "explanation": "知识库说延迟约80ms"}
        ]
    },
    "h03": {
        "is_hallucination": True,
        "hallucination_type": "能力越界",
        "confidence": 0.90,
        "evidence": "知识库为'无（客服系统未接入物流查询接口）'，系统不具备物流查询能力，但回复却给出了'南京转运中心'和'预计明天下午送达'等具体信息。",
        "severity": "high",
        "claims_analysis": [
            {"claim": "包裹目前在南京转运中心", "verdict": "unsupported", "explanation": "系统未接入物流查询接口，无法获取此信息"},
            {"claim": "预计明天下午送达", "verdict": "unsupported", "explanation": "系统无法查询物流进度"}
        ]
    },
    "h04": {
        "is_hallucination": True,
        "hallucination_type": "政策编造",
        "confidence": 0.80,
        "evidence": "回复说'支持电子发票和纸质发票'，但知识库说'暂不支持纸质发票'。另外指引'在备注里填写'也不对，应在'订单详情页申请'。部分正确（电子发票）但纸质发票是编造的。",
        "severity": "high",
        "claims_analysis": [
            {"claim": "支持电子发票", "verdict": "supported", "explanation": "知识库确认支持电子发票"},
            {"claim": "支持纸质发票", "verdict": "contradicted", "explanation": "知识库说暂不支持纸质发票"},
            {"claim": "下单时在备注里写发票抬头和税号", "verdict": "contradicted", "explanation": "应在下单后在订单详情页申请"}
        ]
    },
    "h05": {
        "is_hallucination": True,
        "hallucination_type": "政策编造",
        "confidence": 0.95,
        "evidence": "回复说'满300减50的店铺优惠券'并承诺'直接发到您账户'，但知识库只有'满200减20、满500减60'，没有满300减50的活动。优惠金额和发券能力均为编造。",
        "severity": "high",
        "claims_analysis": [
            {"claim": "有满300减50的优惠券", "verdict": "contradicted", "explanation": "知识库只有满200减20和满500减60"},
            {"claim": "直接发到您账户里", "verdict": "unsupported", "explanation": "知识库未提及自动发券功能"}
        ]
    },
    "h06": {
        "is_hallucination": True,
        "hallucination_type": "参数编造",
        "confidence": 0.95,
        "evidence": "回复说'头层牛皮制作，保修两年'，但知识库是'PU合成革，保修期6个月'。材质和保修期均严重编造。",
        "severity": "high",
        "claims_analysis": [
            {"claim": "头层牛皮制作", "verdict": "contradicted", "explanation": "知识库标注为PU合成革"},
            {"claim": "保修期为两年", "verdict": "contradicted", "explanation": "知识库说保修期6个月"}
        ]
    },
    "h07": {
        "is_hallucination": True,
        "hallucination_type": "能力越界",
        "confidence": 0.85,
        "evidence": "知识库明确说明'退货地址根据商品类别不同而不同，需由系统自动匹配后以短信方式发送，人工客服不可口头告知'，但回复直接给出了完整的地址和张经理收件人信息。",
        "severity": "high",
        "claims_analysis": [
            {"claim": "退货请寄到浙江省杭州市西湖区文三路478号", "verdict": "contradicted", "explanation": "退货地址需系统自动匹配后短信发送，不可口头告知"},
            {"claim": "客服仓库张经理收", "verdict": "unsupported", "explanation": "知识库中无此收件人信息"},
            {"claim": "邮编310012", "verdict": "unsupported", "explanation": "知识库中无此邮编信息"}
        ]
    },
    "h08": {
        "is_hallucination": True,
        "hallucination_type": "政策编造",
        "confidence": 0.85,
        "evidence": "回复说'48小时内发货，顺丰快递，2-3天到货'，但知识库是'24小时内发货，中通/韵达/圆通，3-5天到货'。发货时间、快递公司和到货时间均不一致。",
        "severity": "high",
        "claims_analysis": [
            {"claim": "48小时内发货", "verdict": "contradicted", "explanation": "知识库说24小时内发货"},
            {"claim": "顺丰快递", "verdict": "contradicted", "explanation": "知识库说中通/韵达/圆通"},
            {"claim": "2-3天到货", "verdict": "contradicted", "explanation": "知识库说一般3-5天"}
        ]
    },
    "h09": {
        "is_hallucination": True,
        "hallucination_type": "参数编造",
        "confidence": 0.80,
        "evidence": "知识库说'产品参数中未标注NFC功能'，但回复肯定地说'支持NFC功能，可以用于公交卡、门禁卡和移动支付'。未标注功能不等于不支持，但做出肯定断言构成了参数编造。",
        "severity": "high",
        "claims_analysis": [
            {"claim": "支持NFC功能", "verdict": "unsupported", "explanation": "产品参数中未标注NFC功能"},
            {"claim": "可以用于公交卡、门禁卡和移动支付", "verdict": "unsupported", "explanation": "是否支持NFC及其用途在知识库中无依据"}
        ]
    },
    "h10": {
        "is_hallucination": True,
        "hallucination_type": "能力越界",
        "confidence": 0.90,
        "evidence": "知识库为'无（客服系统未接入退款进度查询接口）'，系统不具备退款进度查询能力，但回复说'退款已在处理中，预计明天到账'。",
        "severity": "high",
        "claims_analysis": [
            {"claim": "退款已经在处理中", "verdict": "unsupported", "explanation": "系统未接入退款进度查询接口"},
            {"claim": "预计明天到账", "verdict": "unsupported", "explanation": "无法查询退款进度"}
        ]
    },
    "h11": {
        "is_hallucination": True,
        "hallucination_type": "信息编造",
        "confidence": 0.95,
        "evidence": "知识库说'本品牌为纯线上电商品牌，无线下门店'，但回复说'在北京、上海、广州、深圳都有线下体验店'。完全虚构了线下门店信息。",
        "severity": "medium",
        "claims_analysis": [
            {"claim": "北京、上海、广州、深圳都有线下体验店", "verdict": "contradicted", "explanation": "纯线上电商品牌，无线下门店"},
            {"claim": "可以在官网门店查询页面查看地址", "verdict": "contradicted", "explanation": "不存在线下门店查询页面"}
        ]
    },
    "h12": {
        "is_hallucination": False,
        "hallucination_type": None,
        "confidence": 0.95,
        "evidence": "回复说'不支持货到付款，支持微信、支付宝和银行卡在线支付'，与知识库'不支持货到付款，支持微信支付、支付宝、银行卡'完全一致。",
        "severity": None,
        "claims_analysis": [
            {"claim": "不支持货到付款", "verdict": "supported", "explanation": "知识库确认不支持货到付款"},
            {"claim": "支持微信、支付宝和银行卡在线支付", "verdict": "supported", "explanation": "与知识库列出的支付方式一致"}
        ]
    },
    "h13": {
        "is_hallucination": True,
        "hallucination_type": "安全误导",
        "confidence": 0.90,
        "evidence": "知识库标注含'视黄醇棕榈酸酯'，并提示'孕妇及哺乳期女性建议咨询医生后使用'，但回复说'成分温和，孕妇可以放心使用，很多孕妈都在回购'。无视了健康风险提示。",
        "severity": "critical",
        "claims_analysis": [
            {"claim": "成分温和，不含酒精香精", "verdict": "incomplete", "explanation": "虽然不含酒精香精，但含视黄醇衍生物"},
            {"claim": "孕妇可以放心使用", "verdict": "contradicted", "explanation": "知识库建议孕妇咨询医生后使用"},
            {"claim": "很多孕妈都在回购", "verdict": "unsupported", "explanation": "知识库中无此信息"}
        ]
    },
    "h14": {
        "is_hallucination": True,
        "hallucination_type": "能力越界",
        "confidence": 0.90,
        "evidence": "知识库为'无（客服系统未接入订单修改接口，需人工后台操作）'，系统不具备订单修改能力，但回复说'已帮您修改为新地址'并给出了具体地址。",
        "severity": "high",
        "claims_analysis": [
            {"claim": "已帮您修改为新地址", "verdict": "unsupported", "explanation": "系统未接入订单修改接口，无法修改"},
            {"claim": "包裹将在明天以新地址发出", "verdict": "unsupported", "explanation": "修改地址操作未被执行"}
        ]
    },
    "h15": {
        "is_hallucination": True,
        "hallucination_type": "信息编造",
        "confidence": 0.85,
        "evidence": "知识库说'品牌介绍中未提及其他品牌关联关系'，但回复说'是XX品牌旗下的子品牌，共享供应链和品控标准，价格更亲民'。编造了与其他品牌的关联关系。",
        "severity": "medium",
        "claims_analysis": [
            {"claim": "是XX品牌旗下的子品牌", "verdict": "unsupported", "explanation": "品牌介绍中未提及其他品牌关联关系"},
            {"claim": "共享同样的供应链和品控标准", "verdict": "unsupported", "explanation": "知识库中无此信息"},
            {"claim": "价格更亲民", "verdict": "unsupported", "explanation": "无价格对比信息"}
        ]
    },
    "h16": {
        "is_hallucination": False,
        "hallucination_type": None,
        "confidence": 0.90,
        "evidence": "回复说'实物拍摄，基本准确，不同手机屏幕可能有轻微色差'，与知识库'因拍摄光线、显示器色差等原因可能与实物存在轻微色差，以实物为准'一致。",
        "severity": None,
        "claims_analysis": [
            {"claim": "商品图片都是实物拍摄", "verdict": "supported", "explanation": "知识库确认图片为实物拍摄"},
            {"claim": "不同手机屏幕可能会有轻微色差", "verdict": "supported", "explanation": "与知识库的色差提示一致"}
        ]
    },
    "h17": {
        "is_hallucination": True,
        "hallucination_type": "参数编造",
        "confidence": 0.95,
        "evidence": "知识库说'接口类型：USB-A输出，附带一根USB-A to Type-C充电线'，但回复说'Type-C接口'。充电头本身是USB-A输出，不是Type-C接口。",
        "severity": "high",
        "claims_analysis": [
            {"claim": "这款充电头是Type-C接口", "verdict": "contradicted", "explanation": "知识库说接口类型为USB-A输出"},
            {"claim": "兼容市面上大多数手机和平板", "verdict": "incomplete", "explanation": "附带USB-A to Type-C线可以兼容，但充电头本身不是Type-C"}
        ]
    },
    "h18": {
        "is_hallucination": True,
        "hallucination_type": "能力越界",
        "confidence": 0.90,
        "evidence": "知识库为'无（客服系统不具备工单升级功能，需转人工处理）'，系统不具备工单升级能力，但回复说'已将投诉升级为高级工单'并承诺'2小时内联系'。",
        "severity": "high",
        "claims_analysis": [
            {"claim": "已升级为高级工单", "verdict": "unsupported", "explanation": "系统不具备工单升级功能"},
            {"claim": "专属客服在2小时内联系您", "verdict": "unsupported", "explanation": "需转人工处理，系统无法自动升级并安排专属客服"}
        ]
    },
    "h19": {
        "is_hallucination": True,
        "hallucination_type": "政策编造",
        "confidence": 0.95,
        "evidence": "知识库说'当前无学生优惠政策'，但回复说'凭学生证享受9折优惠'并指引'选择学生认证'。完全虚构了不存在的学生优惠政策和认证入口。",
        "severity": "high",
        "claims_analysis": [
            {"claim": "凭学生证可以享受9折优惠", "verdict": "contradicted", "explanation": "当前无学生优惠政策"},
            {"claim": "在结算时选择'学生认证'", "verdict": "unsupported", "explanation": "无学生认证功能入口"}
        ]
    },
    "h20": {
        "is_hallucination": True,
        "hallucination_type": "信息遗漏",
        "confidence": 0.65,
        "evidence": "回复说'尺码标准，不偏大也不偏小，按平时尺码选'，但知识库中明确提到'约30%的用户反馈偏大半码，建议脚瘦的用户选小半码'。回复遗漏了偏大的关键信息，可能导致用户选错尺码。这属于信息遗漏型幻觉，边界较模糊。",
        "severity": "low",
        "claims_analysis": [
            {"claim": "尺码标准，不偏大也不偏小", "verdict": "incomplete", "explanation": "知识库有30%用户反馈偏大半码，遗漏了此关键信息"},
            {"claim": "按平时穿的尺码选", "verdict": "incomplete", "explanation": "未提供脚瘦用户选小半码的建议"}
        ]
    },
}
