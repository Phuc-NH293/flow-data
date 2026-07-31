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

function buildDemoSeries(dates, byDate) {
  return dates.map((date, index) => {
    const base = byDate[date];
    const jitter = index % 2 === 0 ? 1.15 : 0.85;
    return {
      date,
      merge: Math.max(1, Math.round((base.merges || 0) + (base.commits || 0) * 0.25 * jitter)),
      verified: Math.max(1, Math.round((base.verified || 0) + (base.commits || 0) * 0.55 * jitter)),
    };
  });
}

function extendDates(dates, byDate) {
  if (!dates.length) return [];
  const first = new Date(`${dates[0]}T00:00:00Z`);
  const last = new Date(`${dates[dates.length - 1]}T00:00:00Z`);
  const out = [];
  const add = (date, factor) => {
    const key = date.toISOString().slice(0, 10);
    const base = byDate[key] || byDate[dates[dates.length - 1]];
    out.push({
      date: key,
      commits: Math.max(1, Math.round((base.commits || 1) * factor)),
      merges: Math.max(1, Math.round((base.merges || 0) * factor + factor * 2)),
      verified: Math.max(1, Math.round((base.verified || 0) * factor + factor * 3)),
      fake: !byDate[key],
    });
  };

  add(new Date(first.getTime() - 24 * 60 * 60 * 1000), 0.75);
  dates.forEach((date, index) => {
    const base = byDate[date];
    out.push({
      date,
      commits: base.commits,
      merges: base.merges,
      verified: base.verified,
      fake: false,
    });
    if (index === dates.length - 1) {
      add(new Date(last.getTime() + 24 * 60 * 60 * 1000), 1.1);
      add(new Date(last.getTime() + 2 * 24 * 60 * 60 * 1000), 1.25);
    }
  });
  return out;
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
  const demoSeries = buildDemoSeries(dates, byDate);
  const extendedSeries = extendDates(dates, byDate);
  const extendedLabels = extendedSeries.map(point => point.date);
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
      labels: extendedLabels,
      datasets: [
        { label: 'Real merge', data: extendedSeries.map(point => point.fake ? null : point.merges), backgroundColor: '#f59e72' },
        { label: 'Real verified', data: extendedSeries.map(point => point.fake ? null : point.verified), backgroundColor: '#71d3b4' },
        { type: 'line', label: 'Demo merge trend', data: extendedSeries.map(point => point.merges), borderColor: '#f59e72', backgroundColor: '#f59e7233', fill: true, tension: 0.35, pointRadius: 2, borderWidth: 2 },
        { type: 'line', label: 'Demo verified trend', data: extendedSeries.map(point => point.verified), borderColor: '#71d3b4', backgroundColor: '#71d3b422', fill: true, tension: 0.35, pointRadius: 2, borderWidth: 2 },
      ],
    },
  }));

  charts.push(new Chart($('verifiedTrend'), {
    type: 'line',
    data: {
      labels: extendedLabels,
      datasets: [{
        label: 'Real verified rate',
        data: extendedSeries.map(point => {
          if (point.fake) return null;
          const total = point.commits || 0;
          return total ? (point.verified / total) * 100 : 0;
        }),
        borderColor: '#f59e72',
        backgroundColor: '#f59e7233',
        fill: true,
        tension: 0.25,
        pointRadius: 3,
        pointHoverRadius: 5,
      }, {
        label: 'Demo verified rate',
        data: extendedSeries.map(point => {
          const total = point.commits || 0;
          const base = total ? (point.verified / total) * 100 : 0;
          return Math.min(100, base * 1.35 + (point.fake ? 12 : 0));
        }),
        borderColor: '#71d3b4',
        backgroundColor: '#71d3b422',
        fill: true,
        tension: 0.25,
        pointRadius: 3,
        pointHoverRadius: 5,
      }],
    },
    options: {
      plugins: {
        legend: {
          labels: {
            color: '#c9d2e3',
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: '#9ca8bb',
          },
          grid: {
            color: '#243041',
          },
        },
        y: {
          min: 0,
          max: 100,
          ticks: {
            color: '#9ca8bb',
            stepSize: 20,
            callback: value => `${value}%`,
          },
          grid: {
            color: '#243041',
          },
        },
      },
    },
  }));
}

$('author').onchange = render;
$('repo').onchange = render;
load();
