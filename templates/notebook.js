const AppNotebook = (() => {
  const STORAGE_KEY = 'ios-app-radar-notebook-v1';
  const FIELDS = {why:'Why it caught my attention', audience:'Target user', problem:'Problem to solve', angle:'My proposed improvement', experiment:'Smallest experiment to test demand'};
  const MAX_ENTRIES = 200, MAX_BYTES = 5 * 1024 * 1024;
  const keyFor = entry => `${entry.country}:${entry.id}`;
  const blankNotes = () => Object.fromEntries(Object.keys(FIELDS).map(key=>[key,'']));
  function text(value, limit, name) {
    if (typeof value !== 'string' || value.length > limit) throw new Error(`Invalid ${name}.`);
    return value;
  }
  function safeURL(value) {
    try { const url=new URL(value);return ['http:','https:'].includes(url.protocol)?url.href:''; } catch {return '';}
  }
  function validDay(value) {
    return typeof value==='string' && /^\d{4}-\d{2}-\d{2}$/.test(value) &&
      Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0,10)===value;
  }
  function validateEntry(raw) {
    if (!raw || typeof raw!=='object' || !/^\d{1,20}$/.test(raw.id) || typeof raw.id!=='string' || !/^[a-z]{2}$/.test(raw.country)) throw new Error('Invalid app identity.');
    if (!validDay(raw.reportDate) || typeof raw.savedAt!=='string' || !Number.isFinite(Date.parse(raw.savedAt))) throw new Error('Invalid saved date.');
    const notes=blankNotes();
    if (!raw.notes || typeof raw.notes!=='object') throw new Error('Missing notes.');
    for (const field of Object.keys(FIELDS)) notes[field]=text(raw.notes[field],4000,'note');
    if (!Array.isArray(raw.charts) || raw.charts.length>100) throw new Error('Invalid chart observations.');
    const charts=raw.charts.map(c=>{
      if (!c || !/^top-(free|paid|grossing):(all|\d+)$/.test(c.key) || !Number.isInteger(c.rank) || c.rank<1 || c.rank>100) throw new Error('Invalid chart rank.');
      return {key:c.key,rank:c.rank,label:text(c.label,300,'chart label')};
    });
    const url=text(raw.url,2048,'app link');
    if (url && !safeURL(url)) throw new Error('App links must use HTTP or HTTPS.');
    return {id:raw.id,country:raw.country,name:text(raw.name,500,'app name'),artist:text(raw.artist,500,'developer'),url,
      savedAt:raw.savedAt,reportDate:raw.reportDate,charts,notes};
  }
  function parse(raw) {
    if (typeof raw!=='string' || raw.length>MAX_BYTES) throw new Error('Notebook file is too large (maximum 5 MB).');
    let data;
    try {data=JSON.parse(raw);} catch {throw new Error('This is not a valid JSON notebook.');}
    if (!data || data.format!=='ios-app-radar-notebook' || data.version!==1 || !Array.isArray(data.entries) || data.entries.length>MAX_ENTRIES) throw new Error('Unsupported notebook format or too many entries (maximum 200).');
    const entries=data.entries.map(validateEntry), seen=new Set();
    for (const entry of entries) {const key=keyFor(entry);if(seen.has(key))throw new Error('The notebook contains duplicate apps.');seen.add(key);}
    return entries;
  }
  function serialize(entries) {
    const raw=JSON.stringify({format:'ios-app-radar-notebook',version:1,entries},null,2);
    parse(raw);return raw;
  }
  function merge(existing, incoming) {
    const entries=new Map(existing.map(e=>[keyFor(e),e]));let added=0;
    for (const entry of incoming) if (!entries.has(keyFor(entry))) {entries.set(keyFor(entry),entry);added++;}
    if (entries.size>MAX_ENTRIES) throw new Error('Notebook limit reached (200 apps). Export and remove some entries first.');
    return {entries:[...entries.values()],added,kept:incoming.length-added};
  }
  function observe(entry,data) {
    if (entry.country!==data.country) return {state:'other-country',charts:[]};
    const current=data.tracking[entry.id];
    if (!current) return {state:'absent',charts:[]};
    const baseline=new Map(entry.charts.map(c=>[c.key,c.rank]));
    return {state:'present',charts:current.charts.map(c=>({...c,gain:data.date>entry.reportDate && baseline.has(c.key)?baseline.get(c.key)-c.rank:null}))};
  }
  function mount(data) {
    const get=id=>document.getElementById(id), root=get('notebook');
    let entries=[],drafts=new Map(),removed=null,storageAvailable=true,unreadable=null;
    const el=(tag,value,className)=>{const node=document.createElement(tag);if(value!==undefined)node.textContent=value;if(className)node.className=className;return node;};
    const status=message=>{get('notebook-status').textContent=message;};
    const read=()=>{const raw=localStorage.getItem(STORAGE_KEY);return raw===null?[]:parse(raw);};
    try {entries=read();} catch(error) {
      try {unreadable=localStorage.getItem(STORAGE_KEY);} catch {storageAvailable=false;}
      status(unreadable!==null?'The stored notebook could not be read. Download its backup for recovery. Editing is disabled to preserve the original.':'Browser storage is unavailable. Notes will last only for this visit; export a backup before leaving.');
    }
    function commit(update,message) {
      if (unreadable!==null) {status('Download the unreadable backup for recovery. Editing is disabled to preserve the original.');return false;}
      // Re-read before mutations so another report tab's saved notes survive.
      if (storageAvailable) {
        try {entries=read();} catch {status('Could not read the latest notebook. Export your open notebook before reloading.');return false;}
      }
      try {
        const next=update(entries);const raw=serialize(next);
        try {localStorage.setItem(STORAGE_KEY,raw);storageAvailable=true;} catch {storageAvailable=false;}
        entries=next;
        status(storageAvailable?message:`${message} Kept only for this visit: browser storage failed. Export before leaving.`);
        return true;
      } catch(error) {status(error.message);return false;}
    }
    function download(raw,name) {
      const url=URL.createObjectURL(new Blob([raw],{type:'application/json'}));
      const link=el('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
    function syncButtons() {
      const saved=new Set(entries.map(keyFor));
      document.querySelectorAll('[data-notebook-save]').forEach(button=>{
        const isSaved=saved.has(button.dataset.notebookSave);
        button.textContent=isSaved?'Open saved idea':'Save idea';button.disabled=unreadable!==null;
        button.setAttribute('aria-label',`${button.textContent}: ${button.dataset.appName}`);
      });
    }
    function openEntry(key) {
      root.open=true;
      const card=[...get('notebook-entries').children].find(c=>c.dataset.entry===key);
      if(card) {card.open=true;card.querySelector('textarea').focus();}
    }
    function saveApp(app) {
      const key=`${data.country}:${app.id}`;
      if (!entries.some(e=>keyFor(e)===key)) {
        const entry=validateEntry({id:app.id,country:data.country,name:app.name||app.id,artist:app.artist||'',url:app.url||'',
          savedAt:new Date().toISOString(),reportDate:data.date,charts:app.charts.map(c=>({key:c.key,rank:c.rank,label:c.label})),notes:blankNotes()});
        if (!commit(existing=>merge(existing,[entry]).entries,'App saved. Add your notes below.')) return;
        render();
      }
      openEntry(key);
    }
    function button(app) {
      const button=el('button');button.type='button';button.dataset.notebookSave=`${data.country}:${app.id}`;button.dataset.appName=app.name||app.id;
      const saved=entries.some(e=>keyFor(e)===button.dataset.notebookSave);
      button.textContent=saved?'Open saved idea':'Save idea';button.setAttribute('aria-label',`${button.textContent}: ${button.dataset.appName}`);button.disabled=unreadable!==null;
      button.addEventListener('click',()=>saveApp(app));return button;
    }
    function render() {
      const container=get('notebook-entries');
      const expanded=new Set([...container.children].filter(c=>c.open).map(c=>c.dataset.entry));
      container.replaceChildren();get('notebook-count').textContent=entries.length;get('notebook-nav-count').textContent=entries.length;
      get('notebook-undo').hidden=removed===null;get('notebook-backup').hidden=unreadable===null;
      if (!entries.length) container.append(el('p',unreadable!==null?'Your original notebook is preserved in browser storage.':'No saved ideas yet. Use Save idea on an app card or a climber row.','empty'));
      for (const entry of [...entries].sort((a,b)=>b.savedAt.localeCompare(a.savedAt))) {
        const key=keyFor(entry), card=el('details');card.dataset.entry=key;card.open=expanded.has(key);card.append(el('summary',`${entry.name} · ${entry.country.toUpperCase()}`));
        const content=el('div',undefined,'content'),link=el('a','View on the App Store');if(safeURL(entry.url))link.href=entry.url;
        content.append(el('p',`${entry.artist} · Saved from report ${entry.reportDate}`,'muted'),link);
        const observation=observe(entry,data);
        if(observation.state==='present') {
          content.append(el('p',`Chart positions in this report (${data.date})`));const list=el('ul');
          for(const c of observation.charts) {
            const delta=c.gain===null?'':c.gain===0?' · unchanged since saved':` · ${c.gain>0?'↑':'↓'} ${Math.abs(c.gain)} places since saved`;
            list.append(el('li',`#${c.rank} · ${c.label}${delta}`));
          }content.append(list);
        } else content.append(el('p',observation.state==='other-country'?`Saved in ${entry.country.toUpperCase()}; this report covers ${data.country.toUpperCase()}.`:`Not observed in this report's configured charts (${data.date}). This does not mean the app was removed from the store.`,'muted'));
        const form=el('form',undefined,'notebook-form'),values=drafts.get(key)||entry.notes;
        for(const [field,labelText] of Object.entries(FIELDS)) {
          const label=el('label',labelText),input=el('textarea');input.rows=2;input.maxLength=4000;input.value=values[field];input.name=field;input.setAttribute('aria-label',`${labelText} — ${entry.name}`);
          input.addEventListener('input',()=>{const values=Object.fromEntries([...form.querySelectorAll('textarea')].map(t=>[t.name,t.value]));drafts.set(key,values);status('Unsaved notes. Choose Save notes to keep them.');});
          label.append(input);form.append(label);
        }
        const actions=el('div',undefined,'actions'),save=el('button','Save notes'),remove=el('button','Remove from notebook');save.type='submit';remove.type='button';
        save.setAttribute('aria-label',`Save notes: ${entry.name}`);remove.setAttribute('aria-label',`Remove from notebook: ${entry.name}`);
        form.addEventListener('submit',event=>{
          event.preventDefault();const notes=Object.fromEntries([...form.querySelectorAll('textarea')].map(t=>[t.name,t.value]));
          if(commit(existing=>{
            if(!existing.some(e=>keyFor(e)===key))throw new Error('This app was removed in another tab. Save it again before editing.');
            return existing.map(e=>keyFor(e)===key?{...e,notes}:e);
          },'Notes saved.'))drafts.delete(key);
        });
        remove.addEventListener('click',()=>{
          let savedEntry;
          if(commit(existing=>{savedEntry=existing.find(e=>keyFor(e)===key);return existing.filter(e=>keyFor(e)!==key);},'App removed. You can undo this removal.')){
            removed=savedEntry?{entry:savedEntry,draft:drafts.get(key)}:null;drafts.delete(key);render();get('notebook-undo').focus();
          }
        });
        actions.append(save,remove);form.append(actions);content.append(form);card.append(content);container.append(card);
      }
      syncButtons();
    }
    get('notebook-export').addEventListener('click',()=>{
      if(drafts.size){status('Save your pending notes before exporting.');return;}
      try {download(serialize(entries),`app-radar-notebook-${new Date().toISOString().slice(0,10)}.json`);status('Notebook exported. Keep this file to restore your saved ideas.');}catch(error){status(error.message);}
    });
    get('notebook-backup').addEventListener('click',()=>download(unreadable,'app-radar-unreadable-backup.json'));
    get('notebook-import').addEventListener('change',async event=>{
      const file=event.target.files[0];event.target.value='';if(!file)return;
      if(drafts.size){status('Save your pending notes before importing.');return;}
      if(file.size>MAX_BYTES){status('Notebook file is too large (maximum 5 MB).');return;}
      try {
        const incoming=parse(await file.text());
        if(unreadable!==null){status('Stored data is unreadable. Download its backup, then clear this site’s notebook storage before importing. The original has not been overwritten.');return;}
        let result;
        if(commit(existing=>{result=merge(existing,incoming);return result.entries;},'Notebook imported.')){
          render();status(`${result.added} apps imported; ${result.kept} existing entries kept unchanged.${storageAvailable?'':' Browser storage failed; export before leaving.'}`);
        }
      }catch(error){status(`Import failed: ${error.message} Your notebook was not changed.`);}
    });
    get('notebook-undo').addEventListener('click',()=>{
      if(!removed)return;const previous=removed;
      if(commit(existing=>merge(existing,[previous.entry]).entries,'Removal undone.')){
        if(previous.draft)drafts.set(keyFor(previous.entry),previous.draft);removed=null;render();openEntry(keyFor(previous.entry));
      }
    });
    window.addEventListener('beforeunload',event=>{if(drafts.size){event.preventDefault();event.returnValue='';}});
    document.querySelector('a[href="#notebook"]').addEventListener('click',()=>{root.open=true;});
    window.addEventListener('storage',event=>{
      if(event.key!==STORAGE_KEY)return;
      try {entries=read();unreadable=null;render();status(drafts.size?'Notebook updated in another tab. Your unsaved notes are still in the editor.':'Notebook updated in another tab.');}
      catch {status('Notebook changed in another tab but could not be read. Export your open notebook before reloading.');}
    });
    render();return {button};
  }
  return {parse,serialize,merge,observe,validateEntry,mount};
})();
if(typeof module!=='undefined')module.exports=AppNotebook;
