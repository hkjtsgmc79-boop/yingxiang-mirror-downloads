'use strict';

const loadButton=document.getElementById('load-catalog');
const statusLine=document.getElementById('catalog-status');
const cards=document.getElementById('catalog-cards');
const log=document.getElementById('catalog-log');
const copyButton=document.getElementById('copy-request');
const copyStatus=document.getElementById('copy-status');

function validateCatalog(data){
  if(!data||data.api_version!=='0.1.0'||data.execution_mode!=='fixture_replay'||!Array.isArray(data.templates)||data.templates.length!==3){
    throw new Error('目录结构与当前接口版本不一致。');
  }
  const ids=new Set();
  for(const item of data.templates){
    if(!item||typeof item.id!=='string'||!/^opera-[a-z]+$/.test(item.id)||ids.has(item.id)||typeof item.name!=='string'||typeof item.description!=='string'||typeof item.preview_url!=='string'||!/^\.\/assets\/[a-z-]+\.svg$/.test(item.preview_url)){
      throw new Error('目录包含无效或重复的模板记录。');
    }
    ids.add(item.id);
  }
  return data;
}

function renderCatalog(data){
  const fragment=document.createDocumentFragment();
  for(const item of data.templates){
    const card=document.createElement('article');
    card.className='template-card';
    const image=document.createElement('img');
    image.className='template-image';image.src=item.preview_url;image.alt=item.name+'原创矢量图标';image.width=240;image.height=176;
    const body=document.createElement('div');body.className='template-body';
    const heading=document.createElement('h3');heading.textContent=item.name;
    const description=document.createElement('p');description.textContent=item.description;
    const code=document.createElement('code');code.textContent=item.id;
    body.append(heading,description,code);card.append(image,body);fragment.append(card);
  }
  cards.replaceChildren(fragment);
}

loadButton.addEventListener('click',async()=>{
  loadButton.disabled=true;statusLine.classList.remove('error');
  statusLine.textContent='正在读取公开目录……';
  const started=performance.now();
  try{
    const response=await fetch('./catalog.json',{cache:'no-store',credentials:'omit',redirect:'error',signal:AbortSignal.timeout(10000)});
    if(!response.ok)throw new Error('HTTP '+response.status+'，目录读取未成功。');
    const data=validateCatalog(await response.json());
    renderCatalog(data);
    const elapsed=Math.round(performance.now()-started);
    statusLine.textContent='读取成功 · HTTP '+response.status+' · '+data.templates.length+' 个模板 · 接口版本 '+data.api_version;
    log.textContent='GET ./catalog.json\nHTTP '+response.status+'\n版本：'+data.api_version+'\n执行模式：'+data.execution_mode+'\n模板数：'+data.templates.length+'\n本次浏览器用时：'+elapsed+' ms\n此请求只读取公开目录，不创建任务或调用模型。';
    loadButton.textContent='重新读取目录';
  }catch(error){
    cards.replaceChildren();statusLine.classList.add('error');
    const message=error&&error.name==='TimeoutError'?'读取超时，请稍后重试。':error&&error.message?error.message:'请检查网络后重试。';
    statusLine.textContent='目录读取失败：'+message;
    log.textContent='GET ./catalog.json\n结果：失败\n原因：'+message+'\n可直接打开 catalog.json 核对地址。';
    loadButton.textContent='重试读取目录';
  }finally{loadButton.disabled=false;}
});

copyButton.addEventListener('click',async()=>{
  const text=document.getElementById('request-example').textContent;
  try{
    if(!navigator.clipboard||!navigator.clipboard.writeText)throw new Error('clipboard unavailable');
    await navigator.clipboard.writeText(text);
    copyStatus.textContent='已复制请求结构。运行时替换本地访问凭证，并按快速开始设置实际服务地址。';
    copyButton.textContent='已复制';
  }catch(error){
    copyStatus.textContent='当前浏览器不允许自动复制，可手动选择上方请求结构。';
  }
});
