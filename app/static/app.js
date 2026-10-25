/* Kimika — page interactions */

function toggleVerification(slug) {
  const el = document.getElementById('verify-' + slug);
  if (el) el.classList.toggle('hidden');
}
