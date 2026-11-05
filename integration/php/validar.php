<?php
// PHP puro (sin framework) con cURL.
const VALIDATOR_URL = 'http://127.0.0.1:8080';
const VALIDATOR_KEY = 'la-misma-clave-de-API_KEYS';

function validarFoto(string $rutaArchivo, string $mime, string $codigoEstudiante): array
{
    $ch = curl_init(VALIDATOR_URL . '/api/v1/photos/validate');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 60,
        CURLOPT_HTTPHEADER => ['X-API-Key: ' . VALIDATOR_KEY],
        CURLOPT_POSTFIELDS => [
            'photo' => new CURLFile($rutaArchivo, $mime, 'foto.jpg'),
            'student_code' => $codigoEstudiante,
        ],
    ]);
    $cuerpo = curl_exec($ch);
    $codigo = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    $json = json_decode($cuerpo, true);
    if ($codigo === 400) {
        return ['status' => 'REJECTED', 'rejection_reasons' => [$json['detail'] ?? 'Archivo inválido'], 'recommendations' => []];
    }
    if ($codigo !== 200) {
        throw new RuntimeException("Error del validador ($codigo)");
    }
    return $json;
}

// Uso con un formulario <input type="file" name="foto">
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_FILES['foto'])) {
    $r = validarFoto($_FILES['foto']['tmp_name'], mime_content_type($_FILES['foto']['tmp_name']), $_POST['codigo'] ?? '');
    echo '<h3>' . htmlspecialchars($r['message'] ?? $r['status']) . '</h3>';
    foreach ($r['rejection_reasons'] as $m) echo '<li>' . htmlspecialchars($m) . '</li>';
}
