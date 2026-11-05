<?php
// app/Services/PhotoValidatorService.php
//
// En config/services.php:
//   'photo_validator' => ['url' => env('PHOTO_VALIDATOR_URL'), 'key' => env('PHOTO_VALIDATOR_KEY')],
// En .env de Laravel:
//   PHOTO_VALIDATOR_URL=http://127.0.0.1:8080
//   PHOTO_VALIDATOR_KEY=la-misma-clave-de-API_KEYS

namespace App\Services;

use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Http;

class PhotoValidatorService
{
    private string $url;
    private string $key;

    public function __construct()
    {
        $this->url = rtrim(config('services.photo_validator.url'), '/');
        $this->key = config('services.photo_validator.key');
    }

    /** Envía la foto y devuelve el resultado (status: APPROVED | REJECTED | MANUAL_REVIEW). */
    public function validate(UploadedFile $foto, string $codigoEstudiante): array
    {
        $resp = Http::withHeaders(['X-API-Key' => $this->key])
            ->timeout(60)
            ->attach('photo', file_get_contents($foto->getRealPath()), $foto->getClientOriginalName(),
                     ['Content-Type' => $foto->getMimeType()])
            ->post("{$this->url}/api/v1/photos/validate", ['student_code' => $codigoEstudiante]);

        if ($resp->status() === 400) {
            return ['success' => false, 'status' => 'REJECTED', 'rejection_reasons' => [$resp->json('detail')],
                    'recommendations' => [], 'criteria' => []];
        }
        $resp->throw();
        return $resp->json();
    }

    public function find(string $validationId): array
    {
        return Http::withHeaders(['X-API-Key' => $this->key])
            ->get("{$this->url}/api/v1/photos/validation/{$validationId}")->throw()->json();
    }

    public function history(string $codigoEstudiante): array
    {
        return Http::withHeaders(['X-API-Key' => $this->key])
            ->get("{$this->url}/api/v1/photos/history", ['student_code' => $codigoEstudiante])->throw()->json();
    }
}
