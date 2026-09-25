document.addEventListener('DOMContentLoaded', () => {
  const searchForm = document.getElementById('flight-search-form');
  const resultsContainer = document.getElementById('flight-results');

  if (searchForm) {
    searchForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const origin = document.getElementById('origin').value;
      const destination = document.getElementById('destination').value;

      resultsContainer.innerHTML = `<div style="text-align:center; padding: 2rem; color: #94a3b8;">Scanning 1,000+ verified partner networks...</div>`;

      try {
        const res = await fetch(`/api/search/flights?origin=${origin}&destination=${destination}`);
        const data = await res.json();

        if (data.ok && data.results.length > 0) {
          resultsContainer.innerHTML = data.results.map(f => `
            <div class="flight-card">
              <div>
                <div style="font-size: 1.25rem; font-weight: 700;">${f.origin} ➔ ${f.destination}</div>
                <div style="color: #94a3b8; font-size: 0.875rem;">Depart: ${f.depart_date} • ${f.transfers === 0 ? 'Direct Flight' : f.transfers + ' Transfer'}</div>
                <div style="color: #64748b; font-size: 0.75rem; margin-top: 0.25rem;">Provider: ${f.gate}</div>
              </div>
              <div style="text-align: right;">
                <div class="flight-price">$${f.price} <span style="font-size:0.875rem; color:#94a3b8;">${f.currency}</span></div>
                <button class="btn-primary" style="margin-top: 0.5rem;" onclick="triggerBridge('${f.booking_url}', '${f.gate}')">
                  Secure Booking Gateway ➔
                </button>
              </div>
            </div>
          `).join('');
        } else {
          resultsContainer.innerHTML = `<div style="text-align:center; padding: 2rem;">No direct fares found. Try searching popular routes like NBO to DXB.</div>`;
        }
      } catch (err) {
        resultsContainer.innerHTML = `<div style="text-align:center; color:#ef4444; padding: 2rem;">Unable to fetch live pricing. Please try again.</div>`;
      }
    });
  }
});

function triggerBridge(targetUrl, partnerName) {
  const modal = document.getElementById('bridge-modal');
  const partnerText = document.getElementById('bridge-partner');
  const progress = document.getElementById('bridge-progress');

  partnerText.innerText = partnerName;
  modal.style.display = 'flex';
  
  setTimeout(() => {
    progress.style.width = '100%';
  }, 50);

  setTimeout(() => {
    window.location.href = targetUrl;
  }, 1500);
}