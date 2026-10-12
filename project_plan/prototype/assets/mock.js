/* HerbMind 原型 · 示例数据（取自《中医经典方证案例研究》真实条目，仅演示用） */
window.MOCK = {
  stats: { formulas: 245, cases: 290, classics: 3, chunks: 535, books: 2 },

  books: [
    { id: 'fz', title: '中医经典方证案例研究', type: '方证 · 医案', author: '陈宝国 主编', dynasty: '现代', status: '已发布', units: 535, current: true },
    { id: 'sh', title: '伤寒论', type: '经典原文 · 方证', author: '张仲景', dynasty: '汉', status: '已接入 · 整理中', units: 398 },
    { id: 'jg', title: '金匮要略', type: '经典原文', author: '张仲景', dynasty: '汉', status: '规划中', units: 0 },
    { id: 'wb', title: '温病条辨', type: '经典原文', author: '吴瑭', dynasty: '清', status: '规划中', units: 0 },
    { id: 'bc', title: '神农本草经', type: '本草', author: '佚名', dynasty: '汉', status: '规划中', units: 0 }
  ],

  shanghan: {
    tree: [
      { chapter: '辨太阳病脉证并治（上）', sections: [ { name: '太阳病提纲', categories: ['太阳中风证', '太阳伤寒证'] } ] },
      { chapter: '辨阳明病脉证并治', sections: [ { name: '阳明病提纲', categories: ['阳明经证', '阳明腑证'] } ] },
      { chapter: '辨少阳病脉证并治', sections: [ { name: '少阳病提纲', categories: ['小柴胡汤证'] } ] },
      { chapter: '辨太阴病脉证并治', sections: [ { name: '太阴病提纲', categories: ['理中丸证'] } ] },
      { chapter: '辨少阴病脉证并治', sections: [ { name: '少阴病提纲', categories: ['四逆汤证', '真武汤证'] } ] },
      { chapter: '辨厥阴病脉证并治', sections: [ { name: '厥阴病提纲', categories: ['乌梅丸证'] } ] }
    ],
    quotes: [
      { id: 'sh1', no: '1', content: '太阳之为病，脉浮，头项强痛而恶寒。' },
      { id: 'sh2', no: '2', content: '太阳病，发热，汗出，恶风，脉缓者，名为中风。' },
      { id: 'sh3', no: '3', content: '太阳病，或已发热，或未发热，必恶寒，体痛，呕逆，脉阴阳俱紧者，名为伤寒。' },
      { id: 'sh35', no: '35', content: '太阳病，头痛发热，身疼腰痛，骨节疼痛，恶风，无汗而喘者，麻黄汤主之。' },
      { id: 'sh96', no: '96', content: '伤寒五六日中风，往来寒热，胸胁苦满，嘿嘿不欲饮食，心烦喜呕……小柴胡汤主之。' }
    ]
  },

  classic: { id: 'shanghan', name: '伤寒论', abbr: '伤寒', dynasty: '汉' },

  tree: [
    { chapter: '第二章《伤寒论》方证案例研究', sections: [
      { name: '第一节 太阳病', categories: ['一、太阳伤寒类方证', '二、太阳中风类方证', '三、太阳温病类方证'] },
      { name: '第二节 阳明病', categories: ['一、阳明经证', '二、阳明腑证'] },
      { name: '第三节 少阳病', categories: ['一、少阳经证', '二、少阳兼证'] }
    ]},
    { chapter: '第三章《温病学》方证案例研究', sections: [
      { name: '第一节 风温', categories: ['一、卫分证', '二、气分证'] },
      { name: '第二节 春温', categories: ['一、热在营分', '二、热入血分'] }
    ]},
    { chapter: '第四章《金匮要略》方证案例研究', sections: [
      { name: '脏腑经络先后病脉证并治', categories: ['一、痉湿暍', '二、百合狐惑阴阳毒'] }
    ]}
  ],

  formulas: [
    { id: 'mahuang', name: '麻黄汤', pinyin: 'má huáng tāng', category: '太阳伤寒类方证',
      efficacy: '发汗解表，宣肺平喘', syndrome: '外感风寒表实证（无汗而喘、脉浮紧）', page: '19-21',
      herbs: [
        { name: '麻黄', dose: '9', unit: 'g', role: 'jun' },
        { name: '桂枝', dose: '6', unit: 'g', role: 'chen' },
        { name: '杏仁', dose: '9', unit: 'g', role: 'zuo' },
        { name: '炙甘草', dose: '3', unit: 'g', role: 'shi' }
      ],
      quotes: ['太阳病，头痛发热，身疼腰痛，骨节疼痛，恶风，无汗而喘者，麻黄汤主之。'] },
    { id: 'guizhi', name: '桂枝汤', pinyin: 'guì zhī tāng', category: '太阳中风类方证',
      efficacy: '解肌发表，调和营卫', syndrome: '外感风寒表虚证（恶风、发热、汗出、脉浮缓）', page: '12-15',
      herbs: [
        { name: '桂枝', dose: '9', unit: 'g', role: 'jun' },
        { name: '白芍', dose: '9', unit: 'g', role: 'chen' },
        { name: '生姜', dose: '9', unit: 'g', role: 'zuo' },
        { name: '大枣', dose: '3', unit: '枚', role: 'zuo' },
        { name: '炙甘草', dose: '6', unit: 'g', role: 'shi' }
      ],
      quotes: ['太阳中风，阳浮而阴弱……桂枝汤主之。'] },
    { id: 'gegen', name: '葛根汤', pinyin: 'gé gēn tāng', category: '太阳兼证',
      efficacy: '发汗解表，升津舒筋', syndrome: '太阳伤寒兼项背强几几', page: '24-26',
      herbs: [
        { name: '葛根', dose: '12', unit: 'g', role: 'jun' },
        { name: '麻黄', dose: '9', unit: 'g', role: 'chen' },
        { name: '桂枝', dose: '6', unit: 'g', role: 'chen' },
        { name: '白芍', dose: '6', unit: 'g', role: 'zuo' },
        { name: '生姜', dose: '9', unit: 'g', role: 'zuo' },
        { name: '大枣', dose: '3', unit: '枚', role: 'zuo' },
        { name: '炙甘草', dose: '6', unit: 'g', role: 'shi' }
      ],
      quotes: ['太阳病，项背强几几，无汗恶风，葛根汤主之。'] }
  ],

  cases: [
    { id: 'c1', title: '麻黄汤证 · 案例一（主治标准）', formula: '麻黄汤', page: '19',
      illness: '徐某，男，23 岁。冬日冒寒远行，当晚即感恶寒发热，头痛身痛，无汗，鼻塞流清涕。',
      exam: '体温 39.2℃，无汗，面赤，舌淡红苔薄白，脉浮紧。',
      diagnosis: '太阳伤寒表实证（风寒束表，肺气失宣）。',
      treatment: '辛温解表，宣肺平喘。',
      prescription: '麻黄 9g、桂枝 6g、杏仁 9g、炙甘草 3g。水煎温服，取微汗。',
      effect: '一剂后汗出热退，诸症顿减，二剂而愈。' },
    { id: 'c2', title: '桂枝汤证 · 案例一（主治标准）', formula: '桂枝汤', page: '12',
      illness: '李某，女，35 岁。受风后恶风发热，自汗出，头痛，鼻鸣干呕。',
      exam: '体温 37.8℃，汗出，舌淡红苔薄白，脉浮缓。',
      diagnosis: '太阳中风表虚证（营卫不和）。',
      treatment: '解肌发表，调和营卫。',
      prescription: '桂枝 9g、白芍 9g、生姜 9g、大枣 3 枚、炙甘草 6g。服后啜热粥，温覆取汗。',
      effect: '二剂后汗止热退，诸症悉平。' }
  ],

  quotes: [
    { id: 'q1', no: '35', classic: '伤寒论', content: '太阳病，头痛发热，身疼腰痛，骨节疼痛，恶风，无汗而喘者，麻黄汤主之。',
      plain: '太阳病见头痛发热、身疼腰痛、骨节疼痛、恶风、无汗而喘，是风寒束表的表实证，用麻黄汤发汗解表。',
      usedBy: ['麻黄汤'] },
    { id: 'q2', no: '12', classic: '伤寒论', content: '太阳中风，阳浮而阴弱，阳浮者，热自发，阴弱者，汗自出……桂枝汤主之。',
      plain: '太阳中风证，营卫不和，卫强营弱，故发热汗出，以桂枝汤调和营卫。',
      usedBy: ['桂枝汤'] },
    { id: 'q3', no: '31', classic: '伤寒论', content: '太阳病，项背强几几，无汗恶风，葛根汤主之。',
      plain: '太阳病见项背拘急不舒、无汗恶风者，用葛根汤解表升津舒筋。',
      usedBy: ['葛根汤'] }
  ],

  score: {
    syndrome: { score: 78, hit: ['恶寒', '无汗', '脉浮紧', '身痛'], miss: ['喘'], extra: ['口渴'] },
    formula:  { score: 83, hit: ['麻黄', '桂枝', '杏仁', '炙甘草'], miss: [], extra: ['生姜'] },
    treatment:{ score: 90 },
    total: 82
  },

  radar: [ { k: '伤寒论', v: 82 }, { k: '温病学', v: 58 }, { k: '金匮要略', v: 66 }, { k: '方剂组成', v: 74 }, { k: '辨证分析', v: 69 } ],

  graph: {
    nodes: [
      { id: 'mahuang', label: 'Formula', name: '麻黄汤', x: 400, y: 240, r: 34 },
      { id: 'guizhi', label: 'Formula', name: '桂枝汤', x: 250, y: 380, r: 30 },
      { id: 'gegen', label: 'Formula', name: '葛根汤', x: 570, y: 380, r: 30 },
      { id: 'ma', label: 'Herb', name: '麻黄', x: 250, y: 120, r: 22 },
      { id: 'gui', label: 'Herb', name: '桂枝', x: 560, y: 140, r: 22 },
      { id: 'xingren', label: 'Herb', name: '杏仁', x: 120, y: 240, r: 20 },
      { id: 'gancao', label: 'Herb', name: '炙甘草', x: 680, y: 240, r: 20 },
      { id: 'synd', label: 'Syndrome', name: '太阳伤寒表实', x: 400, y: 90, r: 30 },
      { id: 'sym1', label: 'Symptom', name: '无汗', x: 250, y: 500, r: 20 },
      { id: 'sym2', label: 'Symptom', name: '脉浮紧', x: 570, y: 500, r: 20 }
    ],
    edges: [
      ['mahuang','ma','COMPOSED_OF'], ['mahuang','gui','COMPOSED_OF'], ['mahuang','xingren','COMPOSED_OF'], ['mahuang','gancao','COMPOSED_OF'],
      ['mahuang','synd','INDICATES'], ['guizhi','synd','INDICATES'],
      ['mahuang','gegen','MODIFIES'], ['guizhi','mahuang','SIMILAR_TO'],
      ['mahuang','sym1','MANIFESTS'], ['mahuang','sym2','MANIFESTS'],
      ['gegen','gui','COMPOSED_OF'], ['guizhi','gui','COMPOSED_OF']
    ]
  }
};
