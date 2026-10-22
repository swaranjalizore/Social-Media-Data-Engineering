const charts = {};
const sentimentColors = {Positive:'#2c9a70', Negative:'#df5a62', Neutral:'#e2a33d'};

async function getJson(url) {
  const response = await fetch(url);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function draw(id, type, labels, datasets, options = {}) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), {
    type, data: {labels, datasets},
    options: {responsive:true, maintainAspectRatio:false, plugins:{legend:{position:'bottom'}}, ...options}
  });
}

function setText(id, value) {
  document.getElementById(id).textContent = value ?? '—';
}

function filtersQuery() {
  const params = new URLSearchParams();
  for (const [key, id] of [['platform','filter-platform'], ['sentiment','filter-sentiment'], ['start_date','filter-start'], ['end_date','filter-end']]) {
    const value = document.getElementById(id).value;
    if (value) params.set(key, value);
  }
  return params.toString();
}

function appendCell(row, value, className = '') {
  const cell = document.createElement('td');
  cell.textContent = value ?? '';
  if (className) cell.className = className;
  row.appendChild(cell);
}

function renderRuns(runs) {
  const body = document.getElementById('runs-table');
  body.replaceChildren();
  for (const run of runs) {
    const row = document.createElement('tr');
    [new Date(run.started_at).toLocaleString(),run.source,run.status,run.total_input,run.new_records,run.duplicate_records,run.processed_records,run.failed_records,run.quality_status,Number(run.execution_seconds).toFixed(2)].forEach(value => appendCell(row, value));
    body.appendChild(row);
  }
  if (!runs.length) {
    const row = document.createElement('tr');
    appendCell(row, 'No runs recorded.', 'text-secondary');
    row.firstChild.colSpan = 10;
    body.appendChild(row);
  }
}

function renderTopPosts(posts) {
  const body = document.getElementById('top-posts-table');
  body.replaceChildren();
  for (const post of posts) {
    const row = document.createElement('tr');
    appendCell(row, post.text);
    appendCell(row, post.platform);
    appendCell(row, post.sentiment);
    appendCell(row, post.post_date);
    appendCell(row, post.engagement);
    body.appendChild(row);
  }
  if (!posts.length) {
    const row = document.createElement('tr');
    appendCell(row, 'No posts match the selected filters.', 'text-secondary');
    row.firstChild.colSpan = 5;
    body.appendChild(row);
  }
}

function renderPlatforms(platforms) {
  const body = document.getElementById('platform-table');
  body.replaceChildren();
  for (const platform of platforms) {
    const row = document.createElement('tr');
    [platform.platform,platform.post_count,Number(platform.total_engagement).toLocaleString(),Number(platform.average_engagement).toFixed(1),`${(Number(platform.average_engagement_rate)*100).toFixed(2)}%`,Number(platform.average_sentiment).toFixed(3),`${platform.positive_posts} / ${platform.neutral_posts} / ${platform.negative_posts}`].forEach(value => appendCell(row,value));
    body.appendChild(row);
  }
  if (!platforms.length) {
    const row = document.createElement('tr');
    appendCell(row,'No platform metrics match the selected filters.','text-secondary');
    row.firstChild.colSpan = 7;
    body.appendChild(row);
  }
}

function renderQuality(quality) {
  const target = document.getElementById('quality-summary');
  target.replaceChildren();
  const latest = quality.latest_run;
  if (!latest) {
    target.textContent = 'No quality report is available yet.';
    return;
  }
  const items = [
    `Quality status: ${latest.quality_status}`,
    `Quality percentage: ${Number(latest.quality_percentage).toFixed(2)}%`,
    `Valid / invalid: ${latest.valid_records} / ${latest.invalid_records}`,
    `Duplicate source rows: ${latest.quality_duplicate_records}`,
    `Missing values: ${latest.missing_values} across ${latest.missing_value_records} records`,
    `Invalid platforms / engagement / sentiment: ${latest.invalid_platforms} / ${latest.invalid_engagement_values} / ${latest.invalid_sentiments}`
  ];
  const list = document.createElement('ul');
  list.className = 'mb-0 ps-3';
  for (const item of items) {
    const li = document.createElement('li');
    li.textContent = item;
    list.appendChild(li);
  }
  target.appendChild(list);
}

async function loadDashboard() {
  const filterMessage = document.getElementById('filter-message');
  filterMessage.classList.add('d-none');
  const query = filtersQuery();
  const suffix = query ? `?${query}` : '';
  try {
    const [dashboard, runs, quality] = await Promise.all([
      getJson(`/api/analytics/dashboard${suffix}`),
      getJson('/api/pipeline/runs'),
      getJson('/api/quality')
    ]);
    const data = dashboard.data;
    const kpis = data.kpis;
    document.getElementById('load-error').classList.toggle('d-none', kpis.total_posts > 0);
    setText('total-posts', kpis.total_posts);
    setText('total-engagement', Number(kpis.total_engagement).toLocaleString());
    setText('average-engagement', Number(kpis.average_engagement).toFixed(1));
    setText('average-rate', `${(Number(kpis.average_engagement_rate) * 100).toFixed(2)}%`);
    setText('average-polarity', Number(kpis.average_sentiment_polarity).toFixed(3));
    setText('total-platforms', kpis.total_platforms);
    setText('total-hashtags', kpis.total_hashtags);
    setText('top-platform', kpis.top_platform || '—');
    setText('positive-posts', kpis.positive_posts);
    setText('neutral-posts', kpis.neutral_posts);
    setText('negative-posts', kpis.negative_posts);

    const latest = runs[0];
    setText('last-run', latest?.started_at ? new Date(latest.started_at).toLocaleString() : 'No runs');
    setText('pipeline-status', latest?.status || '—');
    setText('run-processed', latest ? `${latest.processed_records} / ${latest.new_records}` : '—');
    setText('run-duplicates', latest ? `${latest.duplicate_records} / ${latest.failed_records}` : '—');
    setText('quality-status', latest?.quality_status || '—');
    setText('run-runtime', latest ? `${Number(latest.execution_seconds).toFixed(2)}s` : '—');
    renderRuns(runs);
    renderQuality(quality);
    renderTopPosts(data.top_posts);
    renderPlatforms(data.platforms);

    const sentiments = ['Positive','Neutral','Negative'];
    const distribution = Object.fromEntries(data.sentiment.map(item => [item.sentiment,item]));
    const sentimentLabels = sentiments.map(key=>`${key} · ${distribution[key]?.percentage||0}%`);
    draw('sentiment-chart','doughnut',sentimentLabels,data.sentiment.length ? [{data:sentiments.map(key=>distribution[key]?.count||0),backgroundColor:sentiments.map(key=>sentimentColors[key])}] : [{data:[]}]);

    const dates = [...new Set(data.sentiment_trend.map(item=>item.date))];
    draw('trend-chart','line',dates,sentiments.map(key=>({label:key,data:dates.map(day=>data.sentiment_trend.find(item=>item.date===day&&item.sentiment===key)?.count||0),borderColor:sentimentColors[key],tension:.25,fill:false})));

    draw('platform-chart','bar',data.platforms.map(item=>item.platform),[
      {label:'Posts',data:data.platforms.map(item=>item.post_count),backgroundColor:'#6b8ff0'},
      {label:'Average engagement',data:data.platforms.map(item=>item.average_engagement),backgroundColor:'#37a980'}
    ]);

    draw('date-chart','line',data.engagement_by_date.map(item=>item.date),[
      {label:'Total engagement',data:data.engagement_by_date.map(item=>item.total_engagement),borderColor:'#6b8ff0',tension:.2},
      {label:'Posts',data:data.engagement_by_date.map(item=>item.post_count),borderColor:'#e2a33d',tension:.2,yAxisID:'y1'}
    ],{scales:{y:{beginAtZero:true},y1:{position:'right',beginAtZero:true,grid:{drawOnChartArea:false}}}});

    draw('hour-chart','bar',data.by_hour.map(item=>`${String(item.hour).padStart(2,'0')}:00`),[
      {label:'Posts',data:data.by_hour.map(item=>item.post_count),backgroundColor:'#6b8ff0'},
      {label:'Average engagement',data:data.by_hour.map(item=>item.average_engagement),backgroundColor:'#8c78d8'}
    ]);
    draw('weekday-chart','bar',data.by_weekday.map(item=>item.day_of_week),[
      {label:'Posts',data:data.by_weekday.map(item=>item.post_count),backgroundColor:'#6b8ff0'},
      {label:'Average engagement',data:data.by_weekday.map(item=>item.average_engagement),backgroundColor:'#edaa52'}
    ]);
    draw('hashtag-chart','bar',data.hashtags.map(item=>item.hashtag),[{label:'Uses',data:data.hashtags.map(item=>item.usage_count),backgroundColor:'#8c78d8'}],{indexAxis:'y'});
    draw('hashtag-engagement-chart','bar',data.hashtag_engagement.map(item=>item.hashtag),[{label:'Average engagement',data:data.hashtag_engagement.map(item=>item.average_engagement),backgroundColor:'#37a980'}],{indexAxis:'y'});

    const exportLink = document.getElementById('export-data');
    exportLink.href = `/api/export${suffix}`;
  } catch (error) {
    filterMessage.textContent = error.message;
    filterMessage.classList.remove('d-none');
    document.getElementById('load-error').classList.remove('d-none');
    console.error(error);
  }
}

document.getElementById('dashboard-filters').addEventListener('submit', event => { event.preventDefault(); loadDashboard(); });
document.getElementById('clear-filters').addEventListener('click', () => {
  document.getElementById('dashboard-filters').reset();
  loadDashboard();
});

document.getElementById('run-pipeline').addEventListener('click', async function () {
  const button = this;
  const message = document.getElementById('pipeline-message');
  const label = button.querySelector('.button-label');
  button.disabled = true;
  label.textContent = 'Running pipeline…';
  message.className = 'alert alert-info';
  message.textContent = 'Loading, validating, transforming and storing the local sample data…';
  try {
    const response = await fetch('/api/pipeline/run', {method:'POST'});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Pipeline failed');
    message.className = 'alert alert-success';
    message.textContent = `Pipeline ${result.status}: ${result.processed_records} processed, ${result.duplicate_records} duplicates, ${result.failed_records} failed (${result.quality_status}).`;
    await loadDashboard();
  } catch (error) {
    message.className = 'alert alert-danger';
    message.textContent = `Pipeline error: ${error.message}`;
  } finally {
    button.disabled = false;
    label.textContent = 'Run Data Pipeline';
  }
});

loadDashboard();
