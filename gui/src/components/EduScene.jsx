import React, { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float, Sparkles } from '@react-three/drei';
import * as THREE from 'three';

/* ------------------------------------------------------------------ *
 * Graduation cap — the hero object. Built from primitives so the app
 * ships with no external model file and no network fetch at runtime.
 * ------------------------------------------------------------------ */
function GraduationCap({ busy }) {
  const group = useRef();
  const tassel = useRef();

  useFrame((state, delta) => {
    const t = state.clock.getElapsedTime();
    if (group.current) {
      group.current.rotation.y += delta * (busy ? 1.1 : 0.35);
      group.current.rotation.z = Math.sin(t * 0.6) * 0.06;
    }
    if (tassel.current) {
      // The tassel swings a beat behind the cap, faster while thinking.
      tassel.current.rotation.z = Math.sin(t * (busy ? 5 : 2)) * (busy ? 0.5 : 0.25);
    }
  });

  return (
    <group ref={group} position={[0, 0.1, 0]} scale={1.15}>
      {/* skull cap */}
      <mesh position={[0, -0.3, 0]} castShadow>
        <cylinderGeometry args={[0.62, 0.74, 0.46, 48]} />
        <meshStandardMaterial color="#33459b" roughness={0.4} metalness={0.3} />
      </mesh>

      {/* mortarboard */}
      <mesh position={[0, 0.02, 0]} rotation={[0, Math.PI / 4, 0]} castShadow>
        <boxGeometry args={[2.1, 0.1, 2.1]} />
        <meshStandardMaterial
          color="#2a3a86"
          emissive="#101a4a"
          emissiveIntensity={0.8}
          roughness={0.3}
          metalness={0.6}
        />
      </mesh>

      {/* gold trim under the board */}
      <mesh position={[0, -0.06, 0]} rotation={[0, Math.PI / 4, 0]}>
        <boxGeometry args={[2.0, 0.04, 2.0]} />
        <meshStandardMaterial
          color="#f4b740"
          emissive="#f4b740"
          emissiveIntensity={busy ? 0.9 : 0.4}
          roughness={0.25}
          metalness={0.9}
        />
      </mesh>

      {/* button + tassel */}
      <mesh position={[0, 0.11, 0]}>
        <sphereGeometry args={[0.1, 24, 24]} />
        <meshStandardMaterial color="#f4b740" metalness={1} roughness={0.2} />
      </mesh>
      <group ref={tassel} position={[0, 0.11, 0]}>
        <mesh position={[0.42, -0.28, 0]} rotation={[0, 0, -0.9]}>
          <cylinderGeometry args={[0.018, 0.018, 0.95, 12]} />
          <meshStandardMaterial color="#f4b740" emissive="#8a5f10" emissiveIntensity={0.4} />
        </mesh>
        <mesh position={[0.78, -0.62, 0]}>
          <coneGeometry args={[0.11, 0.34, 16]} />
          <meshStandardMaterial color="#f4b740" metalness={0.7} roughness={0.35} />
        </mesh>
      </group>
    </group>
  );
}

/* ------------------------------------------------------------------ *
 * Books orbiting the cap — each one is a "source" in the catalogue.
 * ------------------------------------------------------------------ */
const BOOK_COLORS = ['#6366f1', '#22d3ee', '#f472b6', '#34d399', '#f4b740'];

function OrbitingBooks({ busy }) {
  const ring = useRef();
  const books = useMemo(
    () =>
      BOOK_COLORS.map((color, i) => ({
        color,
        angle: (i / BOOK_COLORS.length) * Math.PI * 2,
        radius: 2.5 + (i % 2) * 0.35,
        height: Math.sin(i * 1.7) * 0.5,
        spin: 0.4 + i * 0.12,
      })),
    []
  );

  useFrame((state, delta) => {
    if (ring.current) ring.current.rotation.y += delta * (busy ? 0.55 : 0.2);
  });

  return (
    <group ref={ring} rotation={[0.32, 0, 0.12]}>
      {books.map((b, i) => (
        <Float key={i} speed={1.4} floatIntensity={0.7} rotationIntensity={0.5}>
          <group
            position={[
              Math.cos(b.angle) * b.radius,
              b.height,
              Math.sin(b.angle) * b.radius,
            ]}
            rotation={[0.2, b.angle, 0.35]}
          >
            {/* cover */}
            <mesh>
              <boxGeometry args={[0.62, 0.1, 0.46]} />
              <meshStandardMaterial
                color={b.color}
                emissive={b.color}
                emissiveIntensity={busy ? 0.55 : 0.25}
                roughness={0.4}
                metalness={0.3}
              />
            </mesh>
            {/* pages */}
            <mesh position={[0.02, 0, 0]}>
              <boxGeometry args={[0.56, 0.075, 0.42]} />
              <meshStandardMaterial color="#f8fafc" roughness={0.9} />
            </mesh>
          </group>
        </Float>
      ))}
    </group>
  );
}

/* ------------------------------------------------------------------ *
 * Wireframe knowledge globe + a lattice of pencils in the far field.
 * ------------------------------------------------------------------ */
function KnowledgeGlobe({ busy }) {
  const mesh = useRef();
  useFrame((state, delta) => {
    if (mesh.current) {
      mesh.current.rotation.y -= delta * 0.08;
      mesh.current.rotation.x += delta * 0.03;
    }
  });
  return (
    <mesh ref={mesh} scale={3.6}>
      <icosahedronGeometry args={[1, 2]} />
      <meshBasicMaterial
        color={busy ? '#f4b740' : '#4f6bff'}
        wireframe
        transparent
        opacity={0.13}
      />
    </mesh>
  );
}

function Pencil({ position, rotation, color }) {
  return (
    <Float speed={1.1} floatIntensity={1.2} rotationIntensity={0.8}>
      <group position={position} rotation={rotation}>
        <mesh>
          <cylinderGeometry args={[0.055, 0.055, 0.9, 6]} />
          <meshStandardMaterial color={color} roughness={0.6} />
        </mesh>
        <mesh position={[0, 0.55, 0]}>
          <coneGeometry args={[0.055, 0.2, 6]} />
          <meshStandardMaterial color="#f5deb3" roughness={0.7} />
        </mesh>
        <mesh position={[0, -0.52, 0]}>
          <cylinderGeometry args={[0.058, 0.058, 0.14, 6]} />
          <meshStandardMaterial color="#ef4b6b" roughness={0.5} />
        </mesh>
      </group>
    </Float>
  );
}

function SceneContents({ busy }) {
  const camera = useRef();
  useFrame((state) => {
    // Gentle parallax: the scene leans toward the pointer.
    const { x, y } = state.pointer;
    state.camera.position.x += (x * 0.7 - state.camera.position.x) * 0.03;
    state.camera.position.y += (y * 0.4 + 2.3 - state.camera.position.y) * 0.03;
    state.camera.lookAt(0, -0.15, 0);
  });

  return (
    <group ref={camera}>
      <ambientLight intensity={0.8} />
      <hemisphereLight args={['#8ea2ff', '#0b1020', 0.9]} />
      <directionalLight position={[5, 6, 4]} intensity={2.4} color="#ffd784" />
      <directionalLight position={[-6, 2, -4]} intensity={1.4} color="#6366f1" />
      <spotLight position={[0, 6, 2]} angle={0.7} penumbra={0.8} intensity={busy ? 90 : 55} color="#ffe6b0" />
      <pointLight position={[0, 0.5, 3]} intensity={busy ? 6 : 3} color="#f4b740" />

      <KnowledgeGlobe busy={busy} />
      <Float speed={1.6} floatIntensity={0.9} rotationIntensity={0.35}>
        <GraduationCap busy={busy} />
      </Float>
      <OrbitingBooks busy={busy} />

      <Pencil position={[-3.4, 1.6, -1.5]} rotation={[0.4, 0, 0.9]} color="#f4b740" />
      <Pencil position={[3.5, -1.4, -1.2]} rotation={[-0.3, 0, -0.7]} color="#22d3ee" />
      <Pencil position={[2.6, 2.1, -2.2]} rotation={[0.8, 0.3, 0.4]} color="#f472b6" />

      <Sparkles
        count={busy ? 90 : 55}
        scale={[9, 6, 6]}
        size={busy ? 4 : 2.6}
        speed={busy ? 0.9 : 0.3}
        opacity={0.7}
        color="#ffd784"
      />
    </group>
  );
}

export default function EduScene({ busy = false }) {
  return (
    <Canvas
      className="edu-canvas"
      dpr={[1, 1.8]}
      camera={{ position: [0, 2.3, 7.2], fov: 45 }}
      gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
    >
      <SceneContents busy={busy} />
    </Canvas>
  );
}
