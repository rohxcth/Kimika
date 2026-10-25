/* Kimika — page interactions */

function toggleCard(slug) {
  const body  = document.getElementById('body-'  + slug);
  const arrow = document.getElementById('arrow-' + slug);
  if (!body) return;

  const isHidden = body.classList.contains('hidden');
  body.classList.toggle('hidden', !isHidden);
  if (arrow) arrow.innerHTML = isHidden ? '&#9660;' : '&#9654;';
}

function toggleVerification(slug) {
  const el = document.getElementById('verify-' + slug);
  if (el) el.classList.toggle('hidden');
}

function navigateDate(dateStr) {
  if (dateStr) window.location.href = '/?date=' + encodeURIComponent(dateStr);
}
