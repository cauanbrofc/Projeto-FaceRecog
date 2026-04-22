document.addEventListener("DOMContentLoaded", () => {
  // Carrega header e footer
  fetch("header.html").then(res => res.text()).then(data => {
    document.getElementById("header").innerHTML = data;
  });
  fetch("footer.html").then(res => res.text()).then(data => {
    document.getElementById("footer").innerHTML = data;
  });

  // Seletores dos elementos
  const abrirCameraBtn = document.getElementById('abrirCamera');
  const tirarFotoBtn = document.getElementById('tirarFoto');
  const video = document.getElementById('video');
  const canvas = document.getElementById('canvas');
  const ctx = canvas.getContext('2d');

  let streamAtivo = false;

  // Abrir a câmera
  if (abrirCameraBtn) {
    abrirCameraBtn.addEventListener('click', () => {
      if (!streamAtivo) {
        navigator.mediaDevices.getUserMedia({ video: true })
          .then(stream => {
            video.srcObject = stream;
            video.style.display = 'block';
            tirarFotoBtn.disabled = false;
            streamAtivo = true;
          })
          .catch(err => alert('Erro ao acessar a câmera: ' + err));
      }
    });
  }

});