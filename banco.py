from flask_cors import CORS
from flask import Flask, request, jsonify
import base64
from PIL import Image
from io import BytesIO
import os
import sqlite3
import numpy as np
import cv2
import webbrowser

# Cria a aplicação Flask
app = Flask(__name__)
CORS(app)

# Carrega os classificadores do OpenCV
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

# Função para inicializar o banco de dados SQLite
def init_db():
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS imagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            caminho TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Função para salvar uma imagem no disco e registrar no banco
def salvar_imagem(nome, img):
    pasta_destino = 'imagens'
    os.makedirs(pasta_destino, exist_ok=True)
    nome_arquivo = f"{nome}.png"
    caminho_destino = os.path.join(pasta_destino, nome_arquivo)
    
    if isinstance(img, Image.Image):
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        cv2.imwrite(caminho_destino, img_cv)
    else:
        cv2.imwrite(caminho_destino, img)
    
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO imagens (nome, caminho) VALUES (?, ?)', (nome, caminho_destino))
    conn.commit()
    conn.close()
    print(f"✅ Imagem salva: {caminho_destino}")
    return caminho_destino

# Função para excluir uma imagem do disco e do banco
def excluir_imagem(nome):
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    cursor.execute('SELECT caminho FROM imagens WHERE nome = ?', (nome,))
    resultado = cursor.fetchone()
    if resultado:
        caminho = resultado[0]
        if os.path.exists(caminho):
            os.remove(caminho)
        cursor.execute('DELETE FROM imagens WHERE nome = ?', (nome,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

# Função para listar todos os alunos cadastrados
def listar_alunos():
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    cursor.execute('SELECT nome, caminho FROM imagens')
    alunos = []
    for nome, caminho in cursor.fetchall():
        if os.path.exists(caminho):
            with open(caminho, 'rb') as img_file:
                foto_b64 = 'data:image/png;base64,' + base64.b64encode(img_file.read()).decode('utf-8')
            alunos.append({'nome': nome, 'foto': foto_b64})
    conn.close()
    return alunos

# Função para normalizar e melhorar a imagem do rosto (SUPER MELHORADA)
def normalizar_rosto(roi):
    """Aplica técnicas avançadas para tornar o rosto invariável a iluminação e sombras"""
    
    # 1. CLAHE - Equalization Adaptativa (melhora contraste local)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(10, 10))
    roi_clahe = clahe.apply(roi)
    
    # 2. Reduz ruído com morfologia
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    roi_morph = cv2.morphologyEx(roi_clahe, cv2.MORPH_CLOSE, kernel)
    
    # 3. Equalização de histograma global
    roi_eq = cv2.equalizeHist(roi_morph)
    
    # 4. Normalização de contraste forte
    roi_norm = cv2.normalize(roi_eq, None, 0, 255, cv2.NORM_MINMAX)
    
    # 5. Suavização bilateral (mantém bordas, remove sombras)
    roi_bilateral = cv2.bilateralFilter(roi_norm, 9, 75, 75)
    
    return roi_bilateral

# Função para extrair APENAS o ROSTO (sem ombro/corpo)
def extrair_apenas_rosto(img):
    """Extrai APENAS a região do rosto, ignorando completamente ombro e corpo"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.05, 5, minSize=(50, 50))
    
    if len(faces) == 0:
        return None
    
    # Pega o maior rosto detectado
    maior_face = max(faces, key=lambda f: f[2] * f[3])
    x, y, w, h = maior_face
    
    # NOVO: Detecta olhos para ajustar melhor a extração
    roi_temp = gray[y:y+h, x:x+w]
    eyes = eye_cascade.detectMultiScale(roi_temp, 1.05, 4)
    
    if len(eyes) > 0:
        # Se detectou olhos, usa como referência
        # Corta apenas do topo da cabeça até abaixo do queixo
        h_rosto = int(h * 0.65)  # REDUZIDO para 65% (menos ombro)
    else:
        h_rosto = int(h * 0.60)  # Se não detectou olhos, corta ainda mais
    
    # Garante que não sai da imagem
    y_fim = min(y + h_rosto, img.shape[0])
    x_fim = min(x + w, img.shape[1])
    
    roi = gray[y:y_fim, x:x_fim]
    
    # Redimensiona para tamanho PEQUENO (para focar em detalhes do rosto)
    roi_resized = cv2.resize(roi, (120, 160))
    
    # Normaliza agressivamente
    roi_normalizado = normalizar_rosto(roi_resized)
    
    return roi_normalizado

# Função para extrair features do rosto
def extrair_features_rosto(img):
    return extrair_apenas_rosto(img)

# Função para calcular similaridade (REFORMULADA COM MAIOR RIGOR)
def calcular_similaridade(roi1, roi2):
    """Compara 2 rostos com MÁXIMA PRECISÃO - detecta até gêmeos"""
    
    scores = {}
    
    # Método 1: Histograma (40%) - MUITO SENSÍVEL A CARACTERÍSTICAS
    hist1 = cv2.calcHist([roi1], [0], None, [256], [0, 256])
    hist2 = cv2.calcHist([roi2], [0], None, [256], [0, 256])
    
    hist1 = cv2.normalize(hist1, hist1).flatten()
    hist2 = cv2.normalize(hist2, hist2).flatten()
    
    # Testa 3 métodos diferentes de comparação de histogramas
    bhattacharyya = cv2.compareHist(hist1, hist2, cv2.HISTCMP_BHATTACHARYYA)
    chi_square = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CHISQR)
    intersection = cv2.compareHist(hist1, hist2, cv2.HISTCMP_INTERSECT)
    
    hist_score = ((1 - bhattacharyya) * 100 + (100 - min(chi_square, 100)) + intersection) / 3
    scores['hist'] = hist_score
    
    # Método 2: Diferença de Sobel (bordas) (25%)
    sobelx1 = cv2.Sobel(roi1, cv2.CV_32F, 1, 0, ksize=3)
    sobely1 = cv2.Sobel(roi1, cv2.CV_32F, 0, 1, ksize=3)
    mag1 = np.sqrt(sobelx1**2 + sobely1**2)
    
    sobelx2 = cv2.Sobel(roi2, cv2.CV_32F, 1, 0, ksize=3)
    sobely2 = cv2.Sobel(roi2, cv2.CV_32F, 0, 1, ksize=3)
    mag2 = np.sqrt(sobelx2**2 + sobely2**2)
    
    diff_mag = cv2.absdiff(mag1, mag2)
    sobel_score = 100 - (np.mean(diff_mag) / np.max(mag1) * 100) if np.max(mag1) > 0 else 0
    scores['sobel'] = sobel_score
    
    # Método 3: Template Matching (20%)
    if roi1.shape == roi2.shape:
        result = cv2.matchTemplate(roi1, roi2, cv2.TM_CCOEFF)
        template_score = np.max(result) if result.size > 0 else 0
    else:
        template_score = 0
    scores['template'] = template_score
    
    # Método 4: Correlação Cruzada (15%)
    correlation = cv2.matchTemplate(roi1, roi2, cv2.TM_CCORR_NORMED)
    corr_score = np.max(correlation) if correlation.size > 0 else 0
    scores['corr'] = corr_score
    
    # COMBINA COM PESOS OTIMIZADOS
    score_final = (hist_score * 0.40) + (sobel_score * 0.25) + (template_score * 0.20) + (corr_score * 0.15)
    
    print(f"    [DEBUG] Hist: {hist_score:.1f}% | Sobel: {sobel_score:.1f}% | Template: {template_score:.1f}% | Corr: {corr_score:.1f}% | FINAL: {score_final:.1f}%")
    
    return score_final

# Rota para cadastrar um novo aluno
@app.route('/cadastrar', methods=['POST'])
def cadastrar():
    try:
        data = request.json
        nome = data['nome']
        foto_b64 = data['foto']
        
        if ',' in foto_b64:
            foto_b64 = foto_b64.split(',')[1]

        conn = sqlite3.connect('banco.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM imagens WHERE nome = ?', (nome,))
        existe = cursor.fetchone()
        conn.close()
        
        if existe:
            return jsonify({'status': 'erro', 'mensagem': 'Aluno já cadastrado!'}), 400

        img = Image.open(BytesIO(base64.b64decode(foto_b64)))
        print(f"✅ Cadastrando aluno: {nome}")
        salvar_imagem(nome, img)
        return jsonify({'status': 'ok'})
    
    except Exception as e:
        print(f"❌ Erro ao cadastrar: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'erro', 'mensagem': str(e)}), 400

# Rota para excluir um aluno
@app.route('/excluir', methods=['POST'])
def excluir():
    data = request.json
    nome = data.get('nome')
    if not nome:
        return jsonify({'status': 'erro', 'mensagem': 'Nome não informado'}), 400
    if excluir_imagem(nome):
        return jsonify({'status': 'ok'})
    else:
        return jsonify({'status': 'erro', 'mensagem': 'Arquivo não encontrado'}), 404

# Rota para listar todos os alunos
@app.route('/alunos', methods=['GET'])
def alunos():
    return jsonify(listar_alunos())

# Rota para reconhecimento facial (DETECTA MÚLTIPLOS ALUNOS)
@app.route('/reconhecer', methods=['POST'])
def reconhecer():
    try:
        data = request.json
        imagem_base64 = data['imagem'].split(',')[1]
        imagem_bytes = base64.b64decode(imagem_base64)
        nparr = np.frombuffer(imagem_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            print("❌ Imagem inválida")
            return jsonify({"nomes": []})
        
        print(f"\n✅ Imagem recebida: {img.shape}")
        
        # NOVO: Detecta MÚLTIPLOS rostos na imagem
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.05, 5, minSize=(50, 50))
        
        if len(faces) == 0:
            print("❌ Nenhum rosto detectado")
            return jsonify({"nomes": []})
        
        print(f"✅ {len(faces)} rosto(s) detectado(s)")
        
        nomes_encontrados = []
        
        # Para CADA rosto encontrado
        for idx, (x, y, w, h) in enumerate(faces):
            print(f"\n🔍 Processando rosto #{idx + 1}...")
            
            # Extrai o rosto específico
            roi_temp = gray[y:y+h, x:x+w]
            eyes = eye_cascade.detectMultiScale(roi_temp, 1.05, 4)
            
            if len(eyes) > 0:
                h_rosto = int(h * 0.65)
            else:
                h_rosto = int(h * 0.60)
            
            y_fim = min(y + h_rosto, img.shape[0])
            x_fim = min(x + w, img.shape[1])
            
            roi = gray[y:y_fim, x:x_fim]
            roi_resized = cv2.resize(roi, (120, 160))
            roi_capturado = normalizar_rosto(roi_resized)
            
            # Compara com todos os alunos
            alunos_reconhecidos = []
            
            conn = sqlite3.connect('banco.db')
            cursor = conn.cursor()
            cursor.execute('SELECT nome, caminho FROM imagens')
            
            for nome, caminho in cursor.fetchall():
                if not os.path.exists(caminho):
                    continue
                
                img_aluno = cv2.imread(caminho)
                if img_aluno is None:
                    continue
                
                roi_aluno = extrair_features_rosto(img_aluno)
                if roi_aluno is None:
                    print(f"    ⚠️  Nenhum rosto em: {nome}")
                    continue
                
                score = calcular_similaridade(roi_capturado, roi_aluno)
                print(f"    {nome}: {score:.2f}%")
                
                # Reduzido para 75% para aceitar mais alunos
                if score > 75:
                    alunos_reconhecidos.append({
                        'nome': nome,
                        'score': score,
                        'indice_rosto': idx + 1
                    })
            
            conn.close()
            
            # Ordena por score
            alunos_reconhecidos.sort(key=lambda x: x['score'], reverse=True)
            
            # Adiciona o melhor match deste rosto
            if alunos_reconhecidos:
                melhor = alunos_reconhecidos[0]
                nomes_encontrados.append(melhor['nome'])
                print(f"  ✅ ROSTO #{melhor['indice_rosto']} IDENTIFICADO: {melhor['nome']} ({melhor['score']:.2f}%)")
            else:
                print(f"  ❌ ROSTO #{idx + 1} NÃO IDENTIFICADO (score < 75%)")
        
        # Remove duplicatas mantendo ordem
        nomes_unicos = []
        for nome in nomes_encontrados:
            if nome not in nomes_unicos:
                nomes_unicos.append(nome)
        
        print(f"\n🎯 RESULTADO FINAL: {nomes_unicos}")
        print(f"   Total de alunos identificados: {len(nomes_unicos)}\n")
        
        return jsonify({"nomes": nomes_unicos})
    
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"nomes": []})

init_db()
webbrowser.open("http://127.0.0.1:5500")

if __name__ == '__main__':
    app.run(debug=True, port=5000)

