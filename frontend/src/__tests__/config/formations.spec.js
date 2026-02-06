import { describe, it, expect } from 'vitest';
import {
  FORMATIONS,
  FUTSAL_FORMATIONS,
  DEFAULT_FORMATION,
  DEFAULT_FUTSAL_FORMATION,
  getFormations,
  getDefaultFormation,
  getFormationOptions,
} from '../../config/formations';

describe('formations config', () => {
  describe('FORMATIONS (soccer)', () => {
    it('has 11 positions per formation', () => {
      Object.entries(FORMATIONS).forEach(([key, formation]) => {
        expect(formation.positions).toHaveLength(11);
        expect(formation.name).toBe(key);
      });
    });

    it('includes GK in every formation', () => {
      Object.values(FORMATIONS).forEach(formation => {
        const gk = formation.positions.find(p => p.position === 'GK');
        expect(gk).toBeDefined();
      });
    });
  });

  describe('FUTSAL_FORMATIONS', () => {
    it('has 5 positions per formation', () => {
      Object.entries(FUTSAL_FORMATIONS).forEach(([key, formation]) => {
        expect(formation.positions).toHaveLength(5);
        expect(formation.name).toContain(key.replace(' (Diamond)', ''));
      });
    });

    it('includes GK in every formation', () => {
      Object.values(FUTSAL_FORMATIONS).forEach(formation => {
        const gk = formation.positions.find(p => p.position === 'GK');
        expect(gk).toBeDefined();
      });
    });

    it('has expected formation keys', () => {
      expect(Object.keys(FUTSAL_FORMATIONS)).toEqual(
        expect.arrayContaining(['1-2-2', '2-2', '1-2-1', '3-1'])
      );
    });
  });

  describe('defaults', () => {
    it('DEFAULT_FORMATION is a valid soccer formation', () => {
      expect(FORMATIONS[DEFAULT_FORMATION]).toBeDefined();
    });

    it('DEFAULT_FUTSAL_FORMATION is a valid futsal formation', () => {
      expect(FUTSAL_FORMATIONS[DEFAULT_FUTSAL_FORMATION]).toBeDefined();
    });
  });

  describe('getFormations()', () => {
    it('returns soccer formations by default', () => {
      expect(getFormations()).toBe(FORMATIONS);
    });

    it('returns soccer formations for "soccer"', () => {
      expect(getFormations('soccer')).toBe(FORMATIONS);
    });

    it('returns futsal formations for "futsal"', () => {
      expect(getFormations('futsal')).toBe(FUTSAL_FORMATIONS);
    });
  });

  describe('getDefaultFormation()', () => {
    it('returns soccer default by default', () => {
      expect(getDefaultFormation()).toBe(DEFAULT_FORMATION);
    });

    it('returns soccer default for "soccer"', () => {
      expect(getDefaultFormation('soccer')).toBe(DEFAULT_FORMATION);
    });

    it('returns futsal default for "futsal"', () => {
      expect(getDefaultFormation('futsal')).toBe(DEFAULT_FUTSAL_FORMATION);
    });
  });

  describe('getFormationOptions()', () => {
    it('returns soccer options by default', () => {
      const options = getFormationOptions();
      expect(options.length).toBe(Object.keys(FORMATIONS).length);
      options.forEach(opt => {
        expect(opt).toHaveProperty('value');
        expect(opt).toHaveProperty('label');
        expect(FORMATIONS[opt.value]).toBeDefined();
      });
    });

    it('returns futsal options for "futsal"', () => {
      const options = getFormationOptions('futsal');
      expect(options.length).toBe(Object.keys(FUTSAL_FORMATIONS).length);
      options.forEach(opt => {
        expect(opt).toHaveProperty('value');
        expect(opt).toHaveProperty('label');
        expect(FUTSAL_FORMATIONS[opt.value]).toBeDefined();
      });
    });

    it('soccer and futsal options are different', () => {
      const soccerOptions = getFormationOptions('soccer');
      const futsalOptions = getFormationOptions('futsal');
      expect(soccerOptions.length).not.toBe(futsalOptions.length);
    });
  });
});
