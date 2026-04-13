# HOME HEALTH — Integración BLE del Tensiómetro Joytech DBP-6296B (Opción B)

## ROL
Eres un desarrollador Flutter/FlutterFlow experto en Bluetooth Low Energy (BLE) con conexión GATT. Debes implementar la integración completa del tensiómetro de brazo Joytech DBP-6296B en la aplicación Home Health, implementando el protocolo directamente en Dart con `flutter_blue_plus`, SIN usar los SDKs nativos del fabricante.

## DECISIÓN ARQUITECTURAL — Opción B confirmada

Se ha elegido la **Opción B**: implementar el protocolo BLE directamente en Flutter/Dart usando `flutter_blue_plus` y la documentación completa del protocolo (BP-protocol.xlsx). No se usarán los SDKs nativos (.aar de Android ni .xcframework de iOS).

**Justificación**: El protocolo está completamente documentado byte por byte con tramas reales validadas, no requiere handshake ni encriptación, y este enfoque es consistente con la integración del oxímetro. Tiempo estimado: +1 a 2 semanas respecto al oxímetro.

## CONTEXTO TÉCNICO — Diferencias con la báscula

A diferencia de la báscula (advertising pasivo), el tensiómetro **SÍ usa GATT** — igual que el oxímetro. Esto significa que el patrón de conexión es familiar: scan → connect → discoverServices → setNotify → write commands.

| Aspecto | Oxímetro YK-67B1 | Tensiómetro DBP-6296B |
|---------|-------------------|------------------------|
| Mecanismo BLE | GATT Notify | GATT Notify + Write |
| Conexión | Unidireccional (solo recibe) | Bidireccional (recibe Y envía comandos) |
| Service UUID | CDEACD80 | **FFF0** |
| Notify Characteristic | Dentro del servicio | **FFF1** (recibir datos) |
| Write Characteristic | No aplica | **FFF2** (enviar comandos) |
| Inicialización | Ninguna | **Time Sync obligatorio** (comando 0x04) |
| Formato de datos | Bytes crudos sin frame | **Frame completo** con header, checksum, terminator |

**Lo nuevo respecto al oxímetro**: aquí la app no solo escucha, también ENVÍA comandos al dispositivo. Y cada trama tiene una estructura formal con checksum que debe validarse.

---

## BLOQUE 1: PROTOCOLO COMPLETO — Referencia para el parser

### 1.1 UUIDs BLE confirmados por el fabricante

```
Service UUID:                FFF0
Characteristic NOTIFY:       FFF1  ← La app escucha datos aquí
Characteristic WRITE:        FFF2  ← La app envía comandos aquí
Write Type:                  Write With Response
Handshake:                   NO requiere
Encriptación:                NINGUNA
Filtro de scan:              Nombre del dispositivo contiene "DBP"
```

### 1.2 Estructura de trama general (aplica a TODOS los mensajes)

Toda comunicación (App → Device y Device → App) sigue esta estructura:

```
┌──────────────┬─────────────┬──────────────┬──────────────┬──────────┬────────────┐
│ Start Char   │ Data Length  │ Function Word│ Data Block   │ Checksum │ Terminator │
│ 4 bytes      │ 2 bytes     │ 1 byte       │ variable     │ 1 byte   │ 2 bytes    │
│ FA AA AA AF  │ total len   │ cmd/response │ payload      │ sum%256  │ F5 5F      │
└──────────────┴─────────────┴──────────────┴──────────────┴──────────┴────────────┘
```

| Campo | Bytes | Valor | Descripción |
|-------|-------|-------|-------------|
| Start Character | 4 | `FA AA AA AF` | Fijo. Encabezado de toda trama |
| Data Length | 2 | Variable (big-endian) | Longitud TOTAL de la trama completa en bytes |
| Function Word | 1 | Variable | Identifica el tipo de mensaje (ver tabla 1.3) |
| Data Block | 0-12 | Variable | Contenido según el Function Word |
| Checksum | 1 | Calculado | Suma de bytes desde Data Length (inclusive) hasta antes del Checksum, mod 256 |
| Terminator | 2 | `F5 5F` | Fijo. Fin de toda trama |

### 1.3 Tabla de Function Words

| # | FW | Dirección | Descripción | Data Block |
|---|-----|-----------|-------------|------------|
| 1 | `0x04` | App → Device | **Time Sync** (obligatorio tras conectar) | 5 bytes: year(0-99), month(1-12), day(1-31), hour(0-23), minute(0-59) |
| 2 | `0x8C` | Device → App | **Respuesta time sync (bound)** | 7 bytes: tipo ASCII(x2), modelo(x2), extras, total grupos memoria(1-4) |
| 3 | `0x84` | Device → App | **Respuesta time sync (unbound)** | 0 bytes |
| 4 | `0x83` | Device → App | **Resultado de medición** | 12 bytes: systolic(x2), diastolic(x2), HR, IHB, year, month, day, hour, minute, group |
| 5 | `0x0A` | App → Device | **Solicitar descarga de historial** | 0 bytes |
| 6 | `0x83` | Device → App | **Registro histórico** (mismo formato que #4) | 12 bytes |
| 7 | `0x8B` | Device → App | **Fin de descarga de historial** | 0 bytes |

### 1.4 Checksum — Fórmula

```dart
int calculateChecksum(List<int> frameBytes) {
  // Sumar todos los bytes desde Data Length (index 4) hasta antes del Checksum
  int sum = 0;
  for (int i = 4; i < frameBytes.length - 3; i++) {
    sum += frameBytes[i];
  }
  return sum % 256;
}

// Validación con trama real del documento:
// FA AA AA AF 00 16 83 00 81 00 65 44 00 15 07 01 0A 2F 01 [1A] F5 5F
// Suma: 00+16+83+00+81+00+65+44+00+15+07+01+0A+2F+01 = 282
// 282 % 256 = 26 = 0x1A ✓
```

### 1.5 Resultado de medición (FW 0x83) — El mensaje más importante

Contiene sistólica, diastólica, frecuencia cardíaca, arritmia y timestamp. **Se envía 6 veces con intervalo de 20ms al completar la medición** — la app debe deduplicar.

| Byte | Campo | Formato | Ejemplo |
|------|-------|---------|---------|
| 0-1 | Sistólica | 16-bit big-endian, mmHg | 0x00 0x81 = 129 mmHg |
| 2-3 | Diastólica | 16-bit big-endian, mmHg | 0x00 0x65 = 101 mmHg |
| 4 | Frecuencia cardíaca | Directo, bpm | 0x44 = 68 bpm |
| 5 | IHB (arritmia) | 0x00 = no, 0xFF = sí | 0x00 = normal |
| 6 | Año | 0-99 (2000 + valor) | 0x15 = 2021 |
| 7 | Mes | 1-12 | 0x07 = julio |
| 8 | Día | 1-31 | 0x01 |
| 9 | Hora | 0-23 | 0x0A = 10:00 |
| 10 | Minuto | 0-59 | 0x2F = 47 |
| 11 | Grupo | 1-4 | 0x01 |

### 1.6 Time Sync (FW 0x04) — Comando obligatorio

```dart
// Trama de ejemplo del documento para 2020-11-16 14:00:
// FA AA AA AF 00 0F 04 14 0B 10 0E 00 32 F5 5F
// Data block: 14(=20, año 2020) 0B(=11, noviembre) 10(=16) 0E(=14) 00(=0)
// Checksum: 00+0F+04+14+0B+10+0E+00 = 80 = 0x50... 
// Documento dice 0x32=50 decimal ✓
```

### 1.7 Descarga de historial (FW 0x0A)

```
// Trama fija (sin data block):
// FA AA AA AF 00 0A 0A [checksum] F5 5F
// Checksum: 00+0A+0A = 20 = 0x14
// Trama completa: FA AA AA AF 00 0A 0A 14 F5 5F

// El dispositivo responde con:
// - Múltiples tramas 0x83 (una por registro almacenado)
// - Una trama final 0x8B (fin de descarga)
```

---

## BLOQUE 2: CUSTOM ACTIONS — Implementación en Dart

### 2.1 Custom Action: `bpConnect` — Conexión y setup inicial

```dart
// === bpConnect Custom Action ===
// Parámetros: deviceId (String — MAC o UUID del periférico)
// Resultado: actualiza App State con estado de conexión

Future<void> bpConnect(String deviceId) async {
  
  // PASO 1: Obtener referencia al dispositivo
  BluetoothDevice device = BluetoothDevice.fromId(deviceId);
  
  // PASO 2: Conectar
  await device.connect(timeout: Duration(seconds: 10));
  FFAppState().update(() => FFAppState().bpIsConnected = true);
  
  // PASO 3: Descubrir servicios
  List<BluetoothService> services = await device.discoverServices();
  
  // PASO 4: Localizar Service FFF0
  BluetoothService? bpService = services.firstWhere(
    (s) => s.uuid.toString().toUpperCase().contains('FFF0'),
    orElse: () => throw Exception('Service FFF0 not found'),
  );
  
  // PASO 5: Localizar Characteristics
  BluetoothCharacteristic? notifyChar = bpService.characteristics.firstWhere(
    (c) => c.uuid.toString().toUpperCase().contains('FFF1'),
  );
  BluetoothCharacteristic? writeChar = bpService.characteristics.firstWhere(
    (c) => c.uuid.toString().toUpperCase().contains('FFF2'),
  );
  
  // PASO 6: Activar Notify en FFF1
  await notifyChar.setNotifyValue(true);
  
  // PASO 7: Escuchar datos entrantes
  notifyChar.onValueReceived.listen((bytes) {
    _onDataReceived(bytes);
  });
  
  // PASO 8: INMEDIATAMENTE enviar Time Sync
  List<int> timeSyncCmd = _buildTimeSyncCommand(DateTime.now());
  await writeChar.write(timeSyncCmd, withResponse: true);
  
  FFAppState().update(() {
    FFAppState().bpStatusMessage = 'Conectado — sincronizando tiempo...';
  });
  
  // Guardar referencia a writeChar para comandos futuros
  // (almacenar en variable global o en un singleton de servicio)
}
```

### 2.2 Función: `_buildTimeSyncCommand` — Constructor de trama 0x04

```dart
List<int> _buildTimeSyncCommand(DateTime now) {
  int year = now.year - 2000;
  int month = now.month;
  int day = now.day;
  int hour = now.hour;
  int minute = now.minute;
  
  // Total length = 4(start) + 2(length) + 1(fw) + 5(data) + 1(chk) + 2(end) = 15 = 0x000F
  List<int> frame = [
    0xFA, 0xAA, 0xAA, 0xAF,  // Start character
    0x00, 0x0F,                // Data length (15 bytes total)
    0x04,                      // Function word: time sync
    year, month, day, hour, minute,  // Data block (5 bytes)
    0x00,                      // Checksum placeholder
    0xF5, 0x5F,                // Terminator
  ];
  
  // Calcular checksum: suma de bytes 4 hasta length-3 (exclusive)
  int checksum = 0;
  for (int i = 4; i < frame.length - 3; i++) {
    checksum += frame[i];
  }
  frame[frame.length - 3] = checksum % 256;
  
  return frame;
}
```

### 2.3 Función: `_onDataReceived` — Parser principal de tramas

```dart
// Buffer para acumular bytes (las tramas pueden llegar fragmentadas)
List<int> _rxBuffer = [];

// Control de deduplicación (el resultado se envía 6 veces)
String? _lastMeasurementHash;

void _onDataReceived(List<int> bytes) {
  _rxBuffer.addAll(bytes);
  
  // Intentar parsear tramas completas del buffer
  while (_rxBuffer.length >= 10) {  // Trama mínima: 4+2+1+0+1+2 = 10 bytes
    
    // Buscar start character
    int startIdx = -1;
    for (int i = 0; i <= _rxBuffer.length - 4; i++) {
      if (_rxBuffer[i] == 0xFA && _rxBuffer[i+1] == 0xAA &&
          _rxBuffer[i+2] == 0xAA && _rxBuffer[i+3] == 0xAF) {
        startIdx = i;
        break;
      }
    }
    
    if (startIdx == -1) {
      _rxBuffer.clear();  // No hay start character, descartar
      return;
    }
    
    // Descartar bytes basura antes del start
    if (startIdx > 0) {
      _rxBuffer = _rxBuffer.sublist(startIdx);
    }
    
    // ¿Tenemos suficientes bytes para leer el Data Length?
    if (_rxBuffer.length < 6) return;  // Esperar más bytes
    
    int totalLength = (_rxBuffer[4] << 8) | _rxBuffer[5];
    
    // ¿Tenemos la trama completa?
    if (_rxBuffer.length < totalLength) return;  // Esperar más bytes
    
    // Extraer la trama completa
    List<int> frame = _rxBuffer.sublist(0, totalLength);
    _rxBuffer = _rxBuffer.sublist(totalLength);
    
    // Validar terminator
    if (frame[frame.length-2] != 0xF5 || frame[frame.length-1] != 0x5F) {
      debugPrint('BP: Invalid terminator');
      continue;
    }
    
    // Validar checksum
    int expectedChecksum = frame[frame.length - 3];
    int calculatedChecksum = 0;
    for (int i = 4; i < frame.length - 3; i++) {
      calculatedChecksum += frame[i];
    }
    if (calculatedChecksum % 256 != expectedChecksum) {
      debugPrint('BP: Checksum mismatch: expected $expectedChecksum, got ${calculatedChecksum % 256}');
      continue;
    }
    
    // Extraer Function Word y Data Block
    int functionWord = frame[6];
    List<int> dataBlock = frame.sublist(7, frame.length - 3);
    
    // MODO DEBUG: imprimir trama completa
    debugPrint('BP FRAME: ${frame.map((b) => b.toRadixString(16).padLeft(2, "0")).join(" ")}');
    debugPrint('BP FW: 0x${functionWord.toRadixString(16)} | Data: ${dataBlock.map((b) => b.toRadixString(16).padLeft(2, "0")).join(" ")}');
    
    // Dispatch por Function Word
    switch (functionWord) {
      case 0x8C:
        _handleTimeSyncBound(dataBlock);
        break;
      case 0x84:
        _handleTimeSyncUnbound();
        break;
      case 0x83:
        _handleMeasurementResult(dataBlock);
        break;
      case 0x8B:
        _handleHistoryDownloadComplete();
        break;
      default:
        debugPrint('BP: Unknown function word: 0x${functionWord.toRadixString(16)}');
    }
  }
}
```

### 2.4 Función: `_handleMeasurementResult` — Decodificación de medición

```dart
void _handleMeasurementResult(List<int> data) {
  if (data.length < 12) return;
  
  int systolic  = (data[0] << 8) | data[1];
  int diastolic = (data[2] << 8) | data[3];
  int heartRate = data[4];
  bool ihb      = data[5] == 0xFF;
  int year      = 2000 + data[6];
  int month     = data[7];
  int day       = data[8];
  int hour      = data[9];
  int minute    = data[10];
  int group     = data[11];
  
  // === DEDUPLICACIÓN ===
  // El dispositivo envía el resultado 6 veces con 20ms de intervalo.
  // Solo procesar la primera recepción.
  String hash = '$systolic-$diastolic-$heartRate-$year$month$day$hour$minute';
  if (hash == _lastMeasurementHash) return;  // Duplicado, ignorar
  _lastMeasurementHash = hash;
  
  // === VALIDACIÓN DE RANGOS FISIOLÓGICOS ===
  if (systolic < 60 || systolic > 260) {
    debugPrint('BP: Systolic out of range: $systolic');
    return;
  }
  if (diastolic < 30 || diastolic > 160) {
    debugPrint('BP: Diastolic out of range: $diastolic');
    return;
  }
  if (heartRate < 25 || heartRate > 220) {
    debugPrint('BP: Heart rate out of range: $heartRate');
    return;
  }
  
  // === ACTUALIZAR APP STATE ===
  FFAppState().update(() {
    FFAppState().bpSystolic = systolic;
    FFAppState().bpDiastolic = diastolic;
    FFAppState().bpHeartRate = heartRate;
    FFAppState().bpIhb = ihb;
    FFAppState().bpReadingValid = true;
    FFAppState().bpIsMeasuring = false;
    FFAppState().bpStatusMessage = ihb
      ? 'Medición completa — irregularidad detectada'
      : 'Medición completa ✓';
  });
  
  debugPrint('BP RESULT: SYS=$systolic DIA=$diastolic HR=$heartRate IHB=$ihb [$year-$month-$day $hour:$minute] G$group');
}
```

### 2.5 Función: `_handleTimeSyncBound` y `_handleTimeSyncUnbound`

```dart
void _handleTimeSyncBound(List<int> data) {
  // Respuesta 0x8C: el dispositivo está vinculado (bound)
  // data contiene info del modelo y grupos de memoria
  int memoryGroups = data.length >= 7 ? data[6] : 1;
  
  FFAppState().update(() {
    FFAppState().bpStatusMessage = 'Sincronizado — listo para medir';
    FFAppState().bpIsConnected = true;
  });
  
  debugPrint('BP: Time sync OK (bound). Memory groups: $memoryGroups');
}

void _handleTimeSyncUnbound() {
  // Respuesta 0x84: el dispositivo no está vinculado (unbound)
  FFAppState().update(() {
    FFAppState().bpStatusMessage = 'Sincronizado — listo para medir';
    FFAppState().bpIsConnected = true;
  });
  
  debugPrint('BP: Time sync OK (unbound)');
}
```

### 2.6 Custom Action: `bpDownloadHistory` — Descarga de historial

```dart
Future<void> bpDownloadHistory(BluetoothCharacteristic writeChar) async {
  // Construir comando 0x0A (sin data block)
  // Total: 4(start) + 2(length) + 1(fw) + 0(data) + 1(chk) + 2(end) = 10 = 0x000A
  List<int> frame = [
    0xFA, 0xAA, 0xAA, 0xAF,
    0x00, 0x0A,  // Data length (10)
    0x0A,        // Function word: download history
    0x00,        // Checksum placeholder
    0xF5, 0x5F,
  ];
  
  // Checksum: 00+0A+0A = 20 = 0x14
  int checksum = 0;
  for (int i = 4; i < frame.length - 3; i++) {
    checksum += frame[i];
  }
  frame[frame.length - 3] = checksum % 256;
  
  // Enviar
  await writeChar.write(frame, withResponse: true);
  
  FFAppState().update(() {
    FFAppState().bpStatusMessage = 'Descargando historial...';
  });
  
  // Los registros llegarán como tramas 0x83 en el listener de _onDataReceived
  // El fin se señala con trama 0x8B
}

void _handleHistoryDownloadComplete() {
  FFAppState().update(() {
    FFAppState().bpStatusMessage = 'Historial descargado ✓';
  });
  debugPrint('BP: History download complete');
}
```

### 2.7 Custom Action: `bpScan` — Escaneo de dispositivos

```dart
Future<void> bpScan() async {
  FFAppState().update(() => FFAppState().bpIsScanning = true);
  
  // Scan filtrando por nombre que contenga "DBP"
  FlutterBluePlus.startScan(
    timeout: Duration(seconds: 15),
    // No filtrar por Service UUID — filtrar por nombre después
  );
  
  FlutterBluePlus.scanResults.listen((results) {
    for (ScanResult r in results) {
      String name = r.device.platformName;
      if (name.toUpperCase().contains('DBP')) {
        // Encontrado un tensiómetro DBP-6296B
        debugPrint('BP FOUND: $name (${r.device.remoteId})');
        // Agregar a lista de dispositivos encontrados en App State
      }
    }
  });
}
```

---

## BLOQUE 3: SEMÁFORO CLÍNICO — Codificación visual

### 3.1 Rangos de colores

```dart
enum BPCategory { normal, elevated, critical }

BPCategory getSystolicCategory(int systolic) {
  if (systolic < 120) return BPCategory.normal;       // 🟢 Verde
  if (systolic < 140) return BPCategory.elevated;      // 🟡 Amarillo
  return BPCategory.critical;                           // 🔴 Rojo
}

BPCategory getDiastolicCategory(int diastolic) {
  if (diastolic < 80) return BPCategory.normal;        // 🟢 Verde
  if (diastolic < 90) return BPCategory.elevated;      // 🟡 Amarillo
  return BPCategory.critical;                           // 🔴 Rojo
}

BPCategory getHeartRateCategory(int hr) {
  if (hr >= 60 && hr <= 100) return BPCategory.normal; // 🟢 Verde
  if ((hr >= 50 && hr < 60) || (hr > 100 && hr <= 120)) return BPCategory.elevated; // 🟡
  return BPCategory.critical;                           // 🔴 Rojo
}

// Alerta inmediata si: systolic >= 180 || diastolic >= 120 || hr < 50 || hr > 120
bool isEmergencyReading(int systolic, int diastolic, int hr) {
  return systolic >= 180 || diastolic >= 120 || hr < 50 || hr > 120;
}
```

### 3.2 Mensaje de IHB (arritmia)

```
// IMPORTANTE: NO diagnosticar ni alarmar clínicamente.
// Texto informativo solamente:
if (ihb) {
  "Se detectó irregularidad en el ritmo cardíaco durante la medición. Consulta a tu médico si esto persiste."
}
```

---

## BLOQUE 4: PANTALLAS DE UI

### 4.1 Pantalla de Setup del Tensiómetro (`BPSetupPage`)

1. Instrucción: "Enciende tu tensiómetro y asegúrate de que el Bluetooth está activado"
2. Botón "Buscar tensiómetro" → inicia scan
3. Lista de dispositivos encontrados (filtrados por nombre "DBP")
4. Usuario selecciona → guardar ID → conectar → time sync → navegar a medición

### 4.2 Pantalla de Medición (`BPMeasurementPage`)

1. Al entrar: verificar conexión (reconectar si necesario)
2. Instrucción: "Coloca el manguito en tu brazo izquierdo y presiona el botón de inicio en el tensiómetro"
3. Estado "Esperando medición..." (animación)
4. Cuando llega resultado (0x83):
   - Display grande: **SYS / DIA** con colores del semáforo
   - Display secundario: frecuencia cardíaca con icono de corazón
   - Badge de IHB si aplica (⚠️ amarillo con texto informativo)
   - Timestamp de la medición
5. Botones: "Guardar", "Medir de nuevo", "Descargar historial"

### 4.3 Pantalla de Resultados (`BPResultsPage`)

- Sistólica con color del semáforo + clasificación textual ("Normal", "Elevada", "Alta")
- Diastólica con color del semáforo
- Frecuencia cardíaca con color
- Badge de IHB si detectado
- Gráfico de tendencia (últimas 10 mediciones)
- Comparación con medición anterior

---

## BLOQUE 5: APP STATE — Variables a crear

| Variable | Tipo | Persisted | Propósito |
|----------|------|-----------|-----------|
| `bpDeviceId` | String | ✅ Sí | ID del tensiómetro registrado |
| `bpDeviceName` | String | ✅ Sí | Nombre BLE del dispositivo |
| `bpSystolic` | Integer | ❌ No | Presión sistólica (mmHg) |
| `bpDiastolic` | Integer | ❌ No | Presión diastólica (mmHg) |
| `bpHeartRate` | Integer | ❌ No | Frecuencia cardíaca (bpm) |
| `bpIhb` | Boolean | ❌ No | Irregular Heart Beat detectado |
| `bpIsConnected` | Boolean | ❌ No | Dispositivo conectado |
| `bpIsMeasuring` | Boolean | ❌ No | Medición en curso |
| `bpReadingValid` | Boolean | ❌ No | Medición válida lista para guardar |
| `bpStatusMessage` | String | ❌ No | Mensaje de estado para el usuario |
| `bpIsScanning` | Boolean | ❌ No | Scan activo |
| `bpHistoryRecords` | JSON | ❌ No | Registros de historial descargados |

---

## BLOQUE 6: API CALLS AL BACKEND

### 6.1 Guardar medición

```
POST /api/measurements/batch/
Body:
{
  "device_serial": "XX:XX:XX:XX:XX:XX",
  "device_type": "blood_pressure_monitor",
  "measured_at": "2026-04-13T14:47:00Z",
  "measurements": [
    { "measurement_type": "systolic", "value": 129, "unit": "mmHg" },
    { "measurement_type": "diastolic", "value": 101, "unit": "mmHg" },
    { "measurement_type": "heart_rate", "value": 68, "unit": "bpm" },
    { "measurement_type": "ihb", "value": 0, "unit": "boolean" }
  ]
}
```

### 6.2 Guardar historial descargado (batch)

```
POST /api/measurements/batch/
Body:
{
  "device_serial": "XX:XX:XX:XX:XX:XX",
  "device_type": "blood_pressure_monitor",
  "is_historical": true,
  "records": [
    {
      "measured_at": "2026-04-10T08:30:00Z",
      "measurements": [
        { "measurement_type": "systolic", "value": 125, "unit": "mmHg" },
        { "measurement_type": "diastolic", "value": 82, "unit": "mmHg" },
        { "measurement_type": "heart_rate", "value": 72, "unit": "bpm" },
        { "measurement_type": "ihb", "value": 0, "unit": "boolean" }
      ]
    },
    // ... más registros
  ]
}
```

---

## BLOQUE 7: DATOS DE SIMULACIÓN PARA TESTING

```dart
// Trama real del documento: 129/101 mmHg, 68 bpm, sin IHB, 2021-07-01 10:47, grupo 1
final List<int> simulatedMeasurement = [
  0xFA, 0xAA, 0xAA, 0xAF,  // Start
  0x00, 0x16,                // Length: 22
  0x83,                      // FW: measurement result
  0x00, 0x81,                // Systolic: 129
  0x00, 0x65,                // Diastolic: 101
  0x44,                      // Heart rate: 68
  0x00,                      // IHB: no
  0x15,                      // Year: 2021
  0x07,                      // Month: 7
  0x01,                      // Day: 1
  0x0A,                      // Hour: 10
  0x2F,                      // Minute: 47
  0x01,                      // Group: 1
  0x1A,                      // Checksum: 0x1A ✓
  0xF5, 0x5F,                // Terminator
];

// Time sync response (bound)
final List<int> simulatedTimeSyncBound = [
  0xFA, 0xAA, 0xAA, 0xAF,
  0x00, 0x11,
  0x8C,
  0x42, 0x50, 0x00, 0x17, 0x02, 0x0C, 0x02,
  0x38,  // Checksum
  0xF5, 0x5F,
];

// Time sync response (unbound)
final List<int> simulatedTimeSyncUnbound = [
  0xFA, 0xAA, 0xAA, 0xAF,
  0x00, 0x0A,
  0x84,
  0x8E,  // Checksum
  0xF5, 0x5F,
];

// History download complete
final List<int> simulatedHistoryComplete = [
  0xFA, 0xAA, 0xAA, 0xAF,
  0x00, 0x0A,
  0x8B,
  0x95,  // Checksum
  0xF5, 0x5F,
];
```

---

## ORDEN DE EJECUCIÓN

| Fase | Descripción | Sin hardware |
|------|-------------|-------------|
| 1 | Variables de App State | ✅ |
| 2 | Función `calculateChecksum` + tests con tramas del documento | ✅ |
| 3 | Función `_buildTimeSyncCommand` + test | ✅ |
| 4 | Parser completo `_onDataReceived` con buffer y dispatch + tests con tramas simuladas | ✅ |
| 5 | Decodificador `_handleMeasurementResult` + test con trama 129/101/68 | ✅ |
| 6 | Lógica de deduplicación (6 envíos del mismo resultado) | ✅ |
| 7 | Lógica del semáforo clínico | ✅ |
| 8 | Custom Action `bpScan` (filtro por "DBP") | ✅ |
| 9 | Custom Action `bpConnect` (connect + service discovery + time sync) | ✅ |
| 10 | Custom Action `bpDownloadHistory` | ✅ |
| 11 | Pantallas de UI (setup, medición, resultados) | ✅ |
| 12 | API Calls al backend | ✅ |
| 13 | Pantalla de debug con hex dump | ✅ |
| 14 | **Validar con hardware real** | ❌ Requiere dispositivo |

---

## INSTRUCCIONES PARA EL AGENTE

1. **PRIMERO**: Lee este documento completo y los 3 archivos adjuntos del protocolo
2. **SEGUNDO**: Presenta plan de implementación por fases con archivos a crear
3. **TERCERO**: Espera aprobación
4. **CUARTO**: Implementa fases 1-13 (todo sin hardware)
5. **QUINTO**: Entrega checklist de validación para cuando llegue el dispositivo

### Reglas estrictas
- **Time Sync es OBLIGATORIO** — enviar comando 0x04 inmediatamente después de conectar, ANTES de cualquier otra operación
- **Deduplicar resultados** — el dispositivo envía cada medición 6 veces, la app debe procesar solo la primera
- **Validar checksum** de TODA trama recibida — descartar tramas con checksum inválido
- **Buffer de recepción** — las tramas BLE pueden llegar fragmentadas; acumular bytes y parsear cuando haya trama completa
- **No diagnosticar** con IHB — solo mostrar mensaje informativo, nunca alarma clínica
- **Rangos fisiológicos**: rechazar valores fuera de rango (SYS 60-260, DIA 30-160, HR 25-220)
- **Write With Response** — todos los comandos a FFF2 deben usar `withResponse: true`
- **Incluir modo debug** con hex dump de tramas para facilitar depuración con hardware real