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

# Carrega o classificador de rostos do OpenCV
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

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
    
    # Se img for PIL Image, converte para OpenCV
    if isinstance(img, Image.Image):
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        cv2.imwrite(caminho_destino, img_cv)
    else:
        # Se já for array do OpenCV
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

# Função para normalizar e melhorar a imagem do rosto
def normalizar_rosto(roi):
    """Aplica técnicas para tornar o rosto invariável a iluminação"""
    
    # 1. CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    roi_clahe = clahe.apply(roi)
    
    # 2. Normalização de contraste
    roi_norm = cv2.normalize(roi_clahe, None, 0, 255, cv2.NORM_MINMAX)
    
    # 3. Filtro bilateral para suavizar mantendo bordas
    roi_smooth = cv2.bilateralFilter(roi_norm, 9, 75, 75)
    
    return roi_smooth

# Função para extrair features do rosto (MELHORADO)
def extrair_features_rosto(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    
    if len(faces) == 0:
        return None
    
    # Pega o maior rosto detectado
    maior_face = max(faces, key=lambda f: f[2] * f[3])
    x, y, w, h = maior_face
    roi = gray[y:y+h, x:x+w]
    
    # Redimensiona para tamanho padrão
    roi_resized = cv2.resize(roi, (200, 200))
    
    # NOVO: Normaliza para invariância de iluminação
    roi_normalizado = normalizar_rosto(roi_resized)
    
    return roi_normalizado

# Função para calcular similaridade (MELHORADA)
def calcular_similaridade(roi1, roi2):
    """Compara 2 rostos usando múltiplos métodos com mais peso em histograma"""
    
    # Método 1: Histograma (mais robusta a iluminação)
    hist1 = cv2.calcHist([roi1], [0], None, [256], [0, 256])
    hist2 = cv2.calcHist([roi2], [0], None, [256], [0, 256])
    
    hist1 = cv2.normalize(hist1, hist1).flatten()
    hist2 = cv2.normalize(hist2, hist2).flatten()
    
    bhattacharyya = cv2.compareHist(hist1, hist2, cv2.HISTCMP_BHATTACHARYYA)
    hist_score = (1 - bhattacharyya) * 100
    
    # Método 2: Chi-Square Distance (alternativa para histogramas)
    chi_square = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CHISQR)
    chi_score = 100 - min(chi_square, 100)
    
    # Método 3: Diferença absoluta média
    diff = cv2.absdiff(roi1, roi2)
    mae = np.mean(diff)
    mae_score = 100 - (mae / 255 * 100)
    
    # Método 4: MSE (Mean Squared Error)
    mse = np.mean((roi1.astype(float) - roi2.astype(float)) ** 2)
    mse_score = 100 - (mse / 65025 * 100)  # 255^2 = 65025
    
    # Combina os métodos com maior peso em histogramas (mais robustos)
    score_final = (hist_score * 0.4) + (chi_score * 0.3) + (mae_score * 0.2) + (mse_score * 0.1)
    
    return score_final

# Rota para cadastrar um novo aluno
@app.route('/cadastrar', methods=['POST'])
def cadastrar():
    try:
        data = request.json
        nome = data['nome']
        foto_b64 = data['foto']
        
        # Remove o prefixo data:image/...;base64,
        if ',' in foto_b64:
            foto_b64 = foto_b64.split(',')[1]

        conn = sqlite3.connect('banco.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM imagens WHERE nome = ?', (nome,))
        existe = cursor.fetchone()
        conn.close()
        
        if existe:
            return jsonify({'status': 'erro', 'mensagem': 'Aluno já cadastrado!'}), 400

        # Decodifica e salva
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

# Rota para reconhecimento facial
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
        
        print(f"✅ Imagem recebida: {img.shape}")
        
        # Extrai rosto da imagem capturada
        roi_capturado = extrair_features_rosto(img)
        
        if roi_capturado is None:
            print("❌ Nenhum rosto detectado")
            return jsonify({"nomes": []})
        
        print(f"✅ Rosto detectado na captura")
        
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
                continue
            
            # Calcula similaridade
            score = calcular_similaridade(roi_capturado, roi_aluno)
            print(f"  {nome}: {score:.2f}%")
            
            # Aumentado para 70% (mais rigoroso)
            if score > 70:
                alunos_reconhecidos.append({
                    'nome': nome,
                    'score': score
                })
        
        conn.close()
        
        # Ordena e retorna o melhor match
        alunos_reconhecidos.sort(key=lambda x: x['score'], reverse=True)
        nomes = [alunos_reconhecidos[0]['nome']] if alunos_reconhecidos else []
        
        print(f"🎯 RESULTADO: {nomes}")
        return jsonify({"nomes": nomes})
    
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"nomes": []})

init_db()
webbrowser.open("http://127.0.0.1:5500")

if __name__ == '__main__':
    app.run(debug=True, port=5000)

