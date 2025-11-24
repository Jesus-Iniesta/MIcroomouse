/**********************************************
  ESP32 PARA MICROMOUSE CONTROLADO POR PC
  Recibe comandos F,L,R,B
  Ejecuta movimiento y responde:
  S front left right
**********************************************/

// ------ Ultrasonico ------
#define TRIG 15
#define ECHO 2   // con divisor resistivo

// ------ IR ------
#define IR_LEFT 25
#define IR_RIGHT 34  // INPUT only (OK)

// ------ Motores L298N ------
#define ENA 32
#define IN1 27
#define IN2 14

#define ENB 26
#define IN3 13
#define IN4 12

// ---------------- MOTORES ----------------
void motorA_adelante() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
}
void motorA_atras() {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
}
void motorA_stop() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
}

void motorB_adelante() {
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
}
void motorB_atras() {
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
}
void motorB_stop() {
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
}

void avanzar() {
  digitalWrite(ENA, HIGH);
  digitalWrite(ENB, HIGH);
  motorA_adelante();
  motorB_adelante();
}

void retroceder() {
  digitalWrite(ENA, HIGH);
  digitalWrite(ENB, HIGH);
  motorA_atras();
  motorB_atras();
}

void detener() {
  digitalWrite(ENA, LOW);
  digitalWrite(ENB, LOW);
  motorA_stop();
  motorB_stop();
}

void girarIzquierda() {
  digitalWrite(ENA, HIGH);
  digitalWrite(ENB, HIGH);
  motorA_atras();     // rueda izquierda hacia atrás
  motorB_adelante();  // rueda derecha hacia adelante
}

void girarDerecha() {
  digitalWrite(ENA, HIGH);
  digitalWrite(ENB, HIGH);
  motorA_adelante();
  motorB_atras();
}

// Giro rápido en su eje
void girarEnEje() {
  digitalWrite(ENA, HIGH);
  digitalWrite(ENB, HIGH);
  motorA_adelante();
  motorB_atras();
}

// -------- ULTRASONICO --------
float medirDistancia() {
  long duracion;
  digitalWrite(TRIG, LOW);
  delayMicroseconds(5);

  digitalWrite(TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG, LOW);

  duracion = pulseIn(ECHO, HIGH, 30000);
  if (duracion <= 0) return -1;

  return duracion * 0.0343 / 2;
}

// -------- LEER SENSORES Y GENERAR PAREDES --------
int paredFrente() {
  float d = medirDistancia();
  if (d > 0 && d < 12) return 1;  // ajustable
  return 0;
}

int paredIzquierda() {
  int v = digitalRead(IR_LEFT);
  return (v == LOW ? 1 : 0);
}

int paredDerecha() {
  int v = digitalRead(IR_RIGHT);
  return (v == LOW ? 1 : 0);
}


// ---------------- SETUP ----------------
void setup() {
  Serial.begin(115200);

  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);

  pinMode(IR_LEFT, INPUT);
  pinMode(IR_RIGHT, INPUT);

  pinMode(ENA, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);

  pinMode(ENB, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  Serial.println("ESP32 MICROMOUSE READY");
}


// ---------------- LOOP ----------------
void loop() {

  // ¿Hay comandos?
  if (Serial.available()) {
    char cmd = Serial.read();

    // --------- MOVIMIENTOS ---------
    if (cmd == 'F') {
      avanzar();
      delay(600);   // tiempo para avanzar una celda
      detener();
    }
    else if (cmd == 'L') {
      girarIzquierda();
      delay(350);
      detener();
    }
    else if (cmd == 'R') {
      girarDerecha();
      delay(350);
      detener();
    }
    else if (cmd == 'B') {
      retroceder();
      delay(600);
      detener();
    }

    // --------- RESPUESTA DE PAREDES ---------
    int f = paredFrente();
    int l = paredIzquierda();
    int r = paredDerecha();

    Serial.print("S ");
    Serial.print(f);
    Serial.print(" ");
    Serial.print(l);
    Serial.print(" ");
    Serial.println(r);
  }
}
