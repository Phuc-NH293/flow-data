let data = [];
let charts = [];

const $ = id => document.getElementById(id);

function destroyCharts() {
  charts.forEach(chart => chart.destroy());
  charts = [];
}

function groupBy(rows, key) {
  return rows.reduce((acc, row) => {
    acc[row[key]] = acc[row[key]] || [];
    acc[row[key]].push(row);
    return acc;
  }, {});
}

async function load() {
  data = await (await fetch('/api/activity')).json();
  const authors = [...new Set(data.map(row => row.author_key))];
  const repos = [...new Set(data.map(row => row.repository))];

  authors.forEach(value => $('author').insertAdjacentHTML('beforeend', `<option>${value}</option>`));
  repos.forEach(value => $('repo').insertAdjacentHTML('beforeend', `<option>${value}</option>`));
  render();
}

function render() {
  const author = $('author').value;
  const repo = $('repo').value;
  const rows = data.filter(row => (!author || row.author_key === author) && (!repo || row.repository === repo));

  destroyCharts();

  const totalCommits = rows.reduce((sum, row) => sum + Number(row.commit_count), 0);
  const totalMerges = rows.reduce((sum, row) => sum + Number(row.merge_commit_count), 0);
  const verifiedCommits = rows.reduce((sum, row) => sum + Number(row.verified_commit_count), 0);

  $('cards').innerHTML = [
    ['Commits', totalCommits],
    ['Authors', new Set(rows.map(row => row.author_key)).size],
    ['Merge commits', totalMerges],
    ['Verified rate', totalCommits ? `${(verifiedCommits / totalCommits * 100).toFixed(1)}%` : '0%'],
  ].map(([label, value]) => `<div class="metric"><small>${label}</small><strong>${value}</strong></div>`).join('');

  const byDate = {};
  rows.forEach(row => {
    if (!byDate[row.commit_date]) {
      byDate[row.commit_date] = { commits: 0, merges: 0, verified: 0 };
    }
    byDate[row.commit_date].commits += Number(row.commit_count);
    byDate[row.commit_date].merges += Number(row.merge_commit_count);
    byDate[row.commit_date].verified += Number(row.verified_commit_count);
  });

  const dates = Object.keys(byDate).sort();
  charts.push(new Chart($('trend'), {
    type: 'line',
    data: {
      labels: dates,
      datasets: [{
        label: 'Commits',
        data: dates.map(date => byDate[date].commits),
        borderColor: '#71d3b4',
        backgroundColor: '#71d3b433',
        fill: true,
        tension: 0.3,
      }],
    },
  }));

  const byAuthor = groupBy(rows, 'author_key');
  const authors = Object.keys(byAuthor).sort((left, right) =>
    byAuthor[right].reduce((sum, row) => sum + Number(row.commit_count), 0) -
    byAuthor[left].reduce((sum, row) => sum + Number(row.commit_count), 0)
  );
  charts.push(new Chart($('authors'), {
    type: 'bar',
    data: {
      labels: authors,
      datasets: [{
        label: 'Commits',
        data: authors.map(authorName =>
          byAuthor[authorName].reduce((sum, row) => sum + Number(row.commit_count), 0)
        ),
        backgroundColor: '#8b9cf6',
      }],
    },
    options: { indexAxis: 'y' },
  }));

  charts.push(new Chart($('quality'), {
    type: 'bar',
    data: {
      labels: dates,
      datasets: [
        { label: 'Merge', data: dates.map(date => byDate[date].merges), backgroundColor: '#f59e72' },
        { label: 'Verified', data: dates.map(date => byDate[date].verified), backgroundColor: '#71d3b4' },
      ],
    },
  }));

  $('rows').innerHTML = rows.map(row => `
    <tr>
      <td>${row.commit_date}</td>
      <td>${row.author_key}</td>
      <td>${row.commit_count}</td>
      <td>${row.merge_commit_count}</td>
      <td>${row.verified_commit_count}</td>
    </tr>
  `).join('');
}

$('author').onchange = render;
$('repo').onchange = render;
load();
