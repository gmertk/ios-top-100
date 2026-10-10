/* Pure selection functions are shared by the report and Node regression tests. */
const DEFAULT_FILTERS = {category: 'any', chartType: 'any', age: 'any', minGain: 1, mode: 'any', hideGames: false};
function signalCompare(a, b) {
  return Number(b.streak >= 3) - Number(a.streak >= 3) || b.gain - a.gain ||
    b.streak - a.streak || a.rank - b.rank || a.key.localeCompare(b.key);
}
function chartMatches(chart, filters) {
  return (filters.category === 'any' || chart.genre === filters.category) &&
    (filters.chartType === 'any' || chart.feed_type === filters.chartType);
}
function appMatches(app, filters, hidden) {
  return !hidden.apps[app.id] && !hidden.developers[app.artist] &&
    (filters.age === 'any' || (app.age_days !== null && app.age_days !== undefined && app.age_days <= Number(filters.age))) &&
    !(filters.hideGames && app.charts.some(c => c.genre === '6014' || /^7\d{3}$/.test(c.genre)));
}
function selectMovers(data, days, filters, hidden) {
  const windowData = data.windows.find(w => w.days === Number(days));
  if (!windowData) return [];
  const matches = [];
  for (const candidate of windowData.candidates) {
    const app = data.apps[candidate.id];
    if (!appMatches(app, filters, hidden)) continue;
    const signals = candidate.signals.map(s => ({...data.charts[s.key], ...s}))
      .filter(s => chartMatches(s, filters) && s.gain >= Number(filters.minGain) && (filters.mode !== 'sustained' || s.streak >= 3))
      .sort(signalCompare);
    if (signals.length) matches.push({...app, signal: signals[0], rising_charts: signals.length});
  }
  return matches.sort((a,b) => signalCompare(a.signal,b.signal) || a.id.localeCompare(b.id));
}
function selectDiscoveries(data, filters, hidden) {
  return data.discoveries.map(id => data.apps[id]).filter(app => appMatches(app,filters,hidden))
    .map(app => ({...app, matchingCharts: app.charts.filter(c => chartMatches(c,filters)).sort((a,b) => a.rank-b.rank || a.key.localeCompare(b.key))}))
    .filter(app => app.matchingCharts.length)
    .sort((a,b) => a.matchingCharts[0].rank-b.matchingCharts[0].rank || a.age_days-b.age_days || a.id.localeCompare(b.id));
}
if (typeof module !== 'undefined') module.exports = {DEFAULT_FILTERS, signalCompare, selectMovers, selectDiscoveries};

if (typeof document !== 'undefined') {
  const data = JSON.parse(document.getElementById('opportunity-data').textContent);
  const notebook = AppNotebook.mount(data);
  const storageKey = 'ios-app-radar-preferences-v1';
  let hidden = {apps: Object.create(null), developers: Object.create(null)};
  let storageWorks = true;
  const controls = {category:'category', chartType:'chart-type', age:'release-age', minGain:'min-gain', mode:'momentum-mode', hideGames:'hide-games'};
  const get = id => document.getElementById(id);
  function filters() {
    return Object.fromEntries(Object.entries(controls).map(([key,id]) => [key, key === 'hideGames' ? get(id).checked : get(id).value]));
  }
  function applyFilters(value) {
    for (const [key,id] of Object.entries(controls)) {
      if (key === 'hideGames') get(id).checked = value[key] === true;
      else {
        const valid = [...get(id).options].some(option => option.value === String(value[key]));
        get(id).value = valid ? String(value[key]) : String(DEFAULT_FILTERS[key]);
      }
    }
  }
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    if (saved && typeof saved === 'object') {
      applyFilters(saved.filters || {});
      for (const kind of ['apps','developers']) {
        if (saved.hidden && saved.hidden[kind] && typeof saved.hidden[kind] === 'object') {
          for (const [key,label] of Object.entries(saved.hidden[kind])) {
            if (typeof label === 'string') hidden[kind][key] = label;
          }
        }
      }
    }
  } catch { storageWorks = false; }
  function save() {
    try { localStorage.setItem(storageKey,JSON.stringify({filters:filters(),hidden})); }
    catch { storageWorks = false; }
  }
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function safeURL(value) {
    try { const url = new URL(value); return ['https:','http:'].includes(url.protocol) ? url.href : ''; }
    catch { return ''; }
  }
  function appLink(app) {
    const link = element('a',app.name || app.id);
    const url = safeURL(app.url);
    if (url) link.href = url;
    return link;
  }
  function header(app) {
    const node = element('div',undefined,'app');
    if (safeURL(app.artwork)) {
      const image = element('img'); image.src=app.artwork; image.alt=''; image.loading='lazy'; node.append(image);
    }
    const info = element('div'), title = element('h3'); title.append(appLink(app));
    info.append(title,element('small',app.artist || 'Unknown developer')); node.append(info); return node;
  }
  function hideActions(app) {
    const actions = element('div',undefined,'actions');
    actions.append(notebook.button(app));
    const more=element('details',undefined,'card-menu');
    more.append(element('summary','Hide options'));
    const addButton = (label,kind,key,value) => {
      const button = element('button',label); button.type='button';
      button.setAttribute('aria-label',`${label}: ${value}`);
      button.addEventListener('click',() => {hidden[kind][key]=value; save(); render(); get('hidden-manager').querySelector('summary').focus();});
      more.append(button);
    };
    addButton('Hide app','apps',app.id,app.name || app.id);
    if (app.artist) addButton('Hide developer','developers',app.artist,app.artist);
    actions.append(more);
    return actions;
  }
  function dayAt(baseline,index) {
    const day = new Date(`${baseline}T00:00:00Z`); day.setUTCDate(day.getUTCDate()+index); return day.toISOString().slice(0,10);
  }
  function timeline(app,w) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('class','spark'); svg.setAttribute('viewBox','0 0 200 65'); svg.setAttribute('role','img');
    svg.setAttribute('aria-label',`Rank history for ${app.name || app.id}; rank 1 at top. Missing observations are gaps.`);
    const point = (rank,index) => [5+index*190/w.days,5+(rank-1)*55/99];
    const appendSVG = (tag,attrs,title) => {
      const node = document.createElementNS(svg.namespaceURI,tag);
      for (const [key,value] of Object.entries(attrs)) node.setAttribute(key,value);
      if (title) {const t=document.createElementNS(svg.namespaceURI,'title');t.textContent=title;node.append(t);}
      svg.append(node);
    };
    app.signal.ranks.forEach((rank,index,ranks) => {
      if (rank === null) return;
      const [x,y]=point(rank,index);
      if (index && ranks[index-1] !== null) {const [x1,y1]=point(ranks[index-1],index-1);appendSVG('line',{x1,y1,x2:x,y2:y});}
      appendSVG('circle',{cx:x,cy:y,r:3},`${dayAt(w.baseline_date,index)}: #${rank}`);
    });
    return svg;
  }
  function momentumCard(app,w) {
    const card=element('article',undefined,'card'), signal=app.signal;
    card.append(header(app),element('span',signal.pattern,'badge pattern'),element('div',`↑ ${signal.gain} places`,'gain'),
      element('p',`${signal.label} · #${signal.previous} → #${signal.rank} in ${w.days} day${w.days===1?'':'s'}`),timeline(app,w),
      element('small',`${signal.observed_days}/${w.days+1} daily observations · #1 at top`));
    const metrics=element('div',undefined,'metric');
    if (signal.streak) metrics.append(element('span',`${signal.streak} consecutive daily gain${signal.streak===1?'':'s'}`,'badge'));
    metrics.append(element('p',`${app.age_days === null ? 'Release date unavailable' : `Released ${app.age_days} days ago`} · First observed ${app.first_seen}`));
    card.append(metrics);
    const details=element('details'), list=element('ul');
    details.append(element('summary','Inspect the rank evidence'));
    signal.ranks.forEach((rank,index)=>list.append(element('li',`${dayAt(w.baseline_date,index)}: ${rank===null?'No observation':`#${rank}`}`)));
    details.append(list);card.append(details,hideActions(app));return card;
  }
  function discoveryCard(app) {
    const card=element('article',undefined,'card'), chart=app.matchingCharts[0];
    card.append(header(app),element('span',`Released ${app.age_days} days ago`,'badge'),element('p',`#${chart.rank} in ${chart.label}`));
    const details=element('details'), list=element('ul'); details.append(element('summary','Matching chart positions'));
    app.matchingCharts.forEach(c=>list.append(element('li',`#${c.rank} · ${c.label}`)));
    details.append(list);card.append(details,hideActions(app));return card;
  }
  function renderHidden() {
    const container=get('hidden-items');container.replaceChildren();let count=0;
    for (const kind of ['apps','developers']) for (const [key,label] of Object.entries(hidden[kind])) {
      count++;const row=element('div',undefined,'hidden-item'), restore=element('button','Restore');restore.type='button';
      restore.setAttribute('aria-label',`Restore ${kind==='apps'?'app':'developer'}: ${label}`);
      restore.addEventListener('click',()=>{delete hidden[kind][key];save();render();get('hidden-manager').querySelector('summary').focus();});
      row.append(element('span',`${kind==='apps'?'App':'Developer'}: ${label}`),restore);container.append(row);
    }
    get('hidden-count').textContent=count;
    get('restore-hidden').disabled=count===0;
    get('storage-status').textContent=storageWorks?'Stored on this browser only.':'Browser storage is unavailable or invalid. These choices may only last for this visit.';
    if (!count) container.append(element('p','Nothing hidden yet. Use Hide app or Hide developer on a card.','muted'));
  }
  function render() {
    const f=filters(), days=Number(get('window').value), w=data.windows.find(w=>w.days===days);
    const chips=get('active-filters');chips.replaceChildren();
    for(const [key,id] of Object.entries(controls)) {
      if(String(f[key])===String(DEFAULT_FILTERS[key]))continue;
      const label=key==='hideGames'?'Games hidden':get(id).selectedOptions[0].textContent;
      const chip=element('button',`${label} ×`,'filter-chip');chip.type='button';chip.setAttribute('aria-label',`Remove filter: ${label}`);
      chip.addEventListener('click',()=>{applyFilters({...filters(),[key]:DEFAULT_FILTERS[key]});save();render();if(['minGain','mode','hideGames'].includes(key))get('advanced-filters').open=true;get(id).focus();});chips.append(chip);
    }
    const advanced=['minGain','mode','hideGames'].filter(key=>String(f[key])!==String(DEFAULT_FILTERS[key])).length;
    get('advanced-count').textContent=advanced?`· ${advanced} active`:'';
    document.querySelectorAll('[data-window]').forEach(panel=>{panel.hidden=Number(panel.dataset.window)!==days;});
    const container=document.querySelector(`[data-filter-results="${days}"]`);
    if (container) {
      container.replaceChildren();const matches=selectMovers(data,days,f,hidden);
      container.append(element('p',`${matches.length} matching climbers from ${w.candidates.length} total · ${w.baseline_date} → ${dayAt(w.baseline_date,w.days)} · Showing up to 25`,'results-count'));
      if (!matches.length) {
        const empty=element('div',undefined,'empty');empty.append(element('h3','No climbers match these filters'),element('p',f.mode==='sustained'?'Sustained climbs need at least three consecutive daily gains within this window. Try a longer window or choose all rises.':'Try lowering the minimum gain, widening the category or age range, or restoring hidden apps.'));container.append(empty);
      } else {
        const cards=element('div',undefined,'cards');matches.slice(0,5).forEach(app=>cards.append(momentumCard(app,w)));container.append(cards);
        if (matches.length>5) {
          const more=element('details',undefined,'more-climbers');more.append(element('summary',`Explore ${Math.min(matches.length-5,20)} more climbers`));
          const wrap=element('div',undefined,'table-wrap'),table=element('table'),head=element('thead'),tr=element('tr'),body=element('tbody');
          table.append(element('caption','More matching climbers'));
          ['App','Chart','Pattern','Previous','Now','Gain','Notebook'].forEach(label=>tr.append(element('th',label)));head.append(tr);
          matches.slice(5,25).forEach(app=>{
            const row=element('tr'),name=element('td');name.append(appLink(app));row.append(name);
            [app.signal.label,app.signal.pattern,`#${app.signal.previous}`,`#${app.signal.rank}`,`↑ ${app.signal.gain}`].forEach(value=>row.append(element('td',value)));
            const saveCell=element('td');saveCell.append(notebook.button(app));row.append(saveCell);body.append(row);
          });table.append(head,body);wrap.append(table);more.append(wrap);container.append(more);
        }
      }
    }
    const discoveries=selectDiscoveries(data,f,hidden),cards=get('discovery-cards');cards.replaceChildren();
    get('discovery-count').textContent=`${discoveries.length} matching fresh discoveries · Showing up to five`;
    discoveries.slice(0,5).forEach(app=>cards.append(discoveryCard(app)));
    if (!discoveries.length) {const empty=element('div',undefined,'empty');empty.append(element('h3','No fresh discoveries match'),element('p','Try a broader category, chart type, or age range. Hidden apps and developers are excluded.'));cards.append(empty);}
    renderHidden();
  }
  get('opportunity-filters').addEventListener('submit',event=>event.preventDefault());
  get('opportunity-filters').addEventListener('change',()=>{save();render();});
  get('window').addEventListener('change',render);
  get('reset-filters').addEventListener('click',()=>{applyFilters(DEFAULT_FILTERS);save();render();});
  get('restore-hidden').addEventListener('click',()=>{hidden={apps:Object.create(null),developers:Object.create(null)};save();render();});
  document.querySelectorAll('input[name="filter"]').forEach(input=>input.addEventListener('change',()=>{
    const selected=document.querySelector('input[name="filter"]:checked').value;
    document.querySelectorAll('.section-details').forEach(section=>{section.hidden=selected!=='all' && section.dataset.feedType!==selected;});
  }));
  render();
}
