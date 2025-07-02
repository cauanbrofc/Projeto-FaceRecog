##📷 FaceRecog - Sistema de Chamada por Reconhecimento Facial

O FaceRecog é um projeto web com o objetivo de substituir o tradicional processo manual de chamadas por uma abordagem moderna e eficiente utilizando reconhecimento facial. Idealizado para ambientes educacionais, o sistema permite que professores ou responsáveis realizem a chamada de alunos por meio de uma simples captura de imagem, tornando o processo mais ágil, seguro e automatizado.

Esse projeto busca integrar tecnologia e praticidade para reduzir o tempo gasto com presença manual e evitar fraudes. Com isso, melhora a produtividade em sala de aula e traz mais organização para registros de presença.

🛠️ Tecnologias Utilizadas
Frontend: HTML, CSS, JavaScript

Backend: Python (Flask)

Reconhecimento Facial: face_recognition (biblioteca em Python)

Outras libs: OpenCV, NumPy

Integração com GPT: (Opcional - futura implementação para relatórios inteligentes)

🚀 Como Usar o Projeto (Tutorial)
Pré-requisitos
Antes de iniciar, você precisa ter instalado:

Python 3.10 ou superior

Pip (gerenciador de pacotes do Python)

Git (opcional, se for clonar o repositório)

1. Clone o projeto ou baixe os arquivos
bash
Copiar
Editar
git clone https://github.com/seu-usuario/facerecog.git
cd facerecog
Ou apenas baixe o ZIP pelo botão verde “Code > Download ZIP” e extraia.

2. Instale as dependências
No terminal, execute:

bash
Copiar
Editar
pip install -r requirements.txt
Se o arquivo requirements.txt não estiver presente, instale manualmente:

bash
Copiar
Editar
pip install flask face_recognition opencv-python
3. Execute o servidor
Navegue até a pasta do projeto e rode:

bash
Copiar
Editar
python app.py
O servidor Flask iniciará em http://localhost:5000.

4. Acesse a aplicação
Abra o navegador e vá para:

arduino
Copiar
Editar
http://localhost:5000
Você verá a interface da aplicação, onde poderá:

Registrar rostos no sistema

Tirar foto ao vivo via webcam

Fazer a chamada automática com base no reconhecimento

5. Adicionando rostos
Vá até a opção Registrar novo rosto

Informe o nome da pessoa

Tire a foto diretamente na aplicação

O sistema irá salvar a imagem codificada e estará pronto para identificação

6. Fazendo a chamada
Na tela principal:

Clique em Reconhecer rosto

A webcam será ativada e o sistema procurará rostos conhecidos

Quando um rosto for identificado, a presença será automaticamente registrada

📌 Observações
As imagens de rostos ficam salvas em uma pasta local (geralmente known_faces)

Em breve, o sistema poderá contar o número de pessoas na imagem

Integrações futuras com IA (GPT) poderão gerar relatórios de frequência, alertas automáticos e muito mais

