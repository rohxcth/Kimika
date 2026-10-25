/* Kimika — page interactions */

function toggleCard(slug) {
  const body  = document.getElementById('body-'  + slug);
  const arrow = document.getElementById('arrow-' + slug);
  const card  = body && body.closest('.rcard');
  if (!body) return;

  const isHidden = body.classList.contains('hidden');
  body.classList.toggle('hidden', !isHidden);
  if (arrow) arrow.classList.toggle('open', isHidden);
  if (card)  card.classList.toggle('expanded', isHidden);
}

function toggleVerification(slug) {
  const el = document.getElementById('verify-' + slug);
  if (el) el.classList.toggle('hidden');
}

function navigateDate(dateStr) {
  if (dateStr) window.location.href = '/?date=' + encodeURIComponent(dateStr);
}
